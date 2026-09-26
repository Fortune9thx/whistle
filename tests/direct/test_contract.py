"""
Contract-level direct-mode tests for Whistle.py (deployed as the bundled
contracts/build/Whistle.deploy.py -- see conftest.py).

gltest direct-mode's run_nondet mock only ever calls the leader closure
and returns its result directly -- it never invokes validator_fn, so
resolve()'s independent-re-derivation/equivalence check cannot be
exercised end to end here. That logic is proven separately in
test_whistle_lib.py's compare_envelopes/is_well_formed_envelope tests
with no genlayer import at all. These tests instead prove: state machine
transitions, bond escrow/return/slash, decisive vs. refund payout math,
pagination, and every UserError guard that fires deterministically --
using mock_web to feed the leader closure's two real desk fetches.
"""
import json
import re
from datetime import datetime, timezone

import pytest
from gltest.direct.loader import create_address

from conftest import CONTRACT_PATH, TREASURY_HEX, to_hex

import whistle_lib as lib

ANCHOR = datetime(2030, 1, 1, tzinfo=timezone.utc)
ANCHOR_EPOCH = int(ANCHOR.timestamp())


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _desk_a_body(status: str, home, away) -> str:
    status_map = {"FT": "Match Finished", "LIVE": "1H", "PRE": "NS", "POSTPONED": "Postponed", "ABANDONED": "Abandoned"}
    return json.dumps({"events": [{"strStatus": status_map.get(status, status), "intHomeScore": str(home) if home is not None else None, "intAwayScore": str(away) if away is not None else None, "strTimestamp": "t0"}]})


def _desk_b_body(status: str, home, away) -> str:
    status_map = {"FT": "FT", "LIVE": "LIVE", "PRE": "NS", "POSTPONED": "PPD", "ABANDONED": "ABD"}
    return json.dumps({"matchStatus": status_map.get(status, status), "homeGoals": home, "awayGoals": away, "lastUpdate": "t1"})


def mock_both_desks(direct_vm, fixture_id, home: int | None = 2, away: int | None = 1, status_a="FT", status_b="FT", home_b=None, away_b=None):
    if home_b is None:
        home_b = home
    if away_b is None:
        away_b = away
    url_a = lib.build_desk_url("desk_a", fixture_id)
    url_b = lib.build_desk_url("desk_b", fixture_id)
    direct_vm.mock_web(re.escape(url_a), {"body": _desk_a_body(status_a, home, away), "status": 200})
    direct_vm.mock_web(re.escape(url_b), {"body": _desk_b_body(status_b, home_b, away_b), "status": 200})


def _deploy(direct_deploy):
    return direct_deploy(CONTRACT_PATH, TREASURY_HEX)


def _open_fixture(direct_vm, direct_deploy, creator, fixture_id="fx-1", kickoff=None):
    if kickoff is None:
        kickoff = ANCHOR_EPOCH + lib.MIN_LEAD + 3600
    direct_vm.warp(_iso(ANCHOR_EPOCH))
    contract = _deploy(direct_deploy)
    direct_vm.sender = creator
    direct_vm.value = lib.CREATE_BOND
    contract.create_fixture(fixture_id, "Real Madrid", "Bayern Munich", kickoff)
    direct_vm.value = 0
    return contract, fixture_id, kickoff


def _resolve_decisive(direct_vm, contract, fixture_id, kickoff, resolver, home=2, away=1):
    mock_both_desks(direct_vm, fixture_id, home=home, away=away)
    direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
    direct_vm.sender = resolver
    direct_vm.value = lib.RESOLVE_BOND
    verdict = contract.resolve(fixture_id)
    direct_vm.value = 0
    return verdict


# ---------------------------------------------------------------------------
# create_fixture
# ---------------------------------------------------------------------------

class TestCreateFixture:
    def test_happy_path_and_bond_escrow(self, direct_vm, direct_deploy, direct_alice):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "OPEN"
        assert fixture["creator"].lower() == to_hex(direct_alice).lower()
        assert fixture["kickoff_unix"] == kickoff
        assert fixture["create_bond_returned"] is False

    def test_rejects_below_min_lead(self, direct_vm, direct_deploy, direct_alice):
        direct_vm.warp(_iso(ANCHOR_EPOCH))
        contract = _deploy(direct_deploy)
        direct_vm.sender = direct_alice
        direct_vm.value = lib.CREATE_BOND
        with direct_vm.expect_revert("below_min_lead"):
            contract.create_fixture("fx-1", "A", "B", ANCHOR_EPOCH + lib.MIN_LEAD - 1)

    def test_rejects_home_equals_away(self, direct_vm, direct_deploy, direct_alice):
        direct_vm.warp(_iso(ANCHOR_EPOCH))
        contract = _deploy(direct_deploy)
        direct_vm.sender = direct_alice
        direct_vm.value = lib.CREATE_BOND
        with direct_vm.expect_revert("home_equals_away"):
            contract.create_fixture("fx-1", "A", "A", ANCHOR_EPOCH + lib.MIN_LEAD)

    def test_rejects_duplicate_fixture_id(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.CREATE_BOND
        with direct_vm.expect_revert("duplicate_fixture"):
            contract.create_fixture(fixture_id, "C", "D", kickoff + 3600)

    def test_rejects_wrong_bond_amount(self, direct_vm, direct_deploy, direct_alice):
        direct_vm.warp(_iso(ANCHOR_EPOCH))
        contract = _deploy(direct_deploy)
        direct_vm.sender = direct_alice
        direct_vm.value = lib.CREATE_BOND - 1
        with direct_vm.expect_revert("wrong_bond_amount"):
            contract.create_fixture("fx-1", "A", "B", ANCHOR_EPOCH + lib.MIN_LEAD)

    def test_creator_open_cap(self, direct_vm, direct_deploy, direct_alice):
        direct_vm.warp(_iso(ANCHOR_EPOCH))
        contract = _deploy(direct_deploy)
        direct_vm.sender = direct_alice
        for i in range(lib.MAX_OPEN_PER_CREATOR):
            direct_vm.value = lib.CREATE_BOND
            contract.create_fixture(f"fx-{i}", "A", "B", ANCHOR_EPOCH + lib.MIN_LEAD + i)
        direct_vm.value = lib.CREATE_BOND
        with direct_vm.expect_revert("creator_cap_reached"):
            contract.create_fixture("fx-overflow", "A", "B", ANCHOR_EPOCH + lib.MIN_LEAD)


# ---------------------------------------------------------------------------
# place_bet
# ---------------------------------------------------------------------------

class TestPlaceBet:
    def test_bet_before_kickoff_and_top_up_same_side(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        pos = contract.get_position(fixture_id, to_hex(direct_bob))
        assert pos["outcome"] == "HOME"
        assert pos["amount"] == lib.MIN_BET * 2

    def test_switch_side_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.value = lib.MIN_BET
        with direct_vm.expect_revert("side_locked"):
            contract.place_bet(fixture_id, "AWAY")

    def test_bet_after_kickoff_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.warp(_iso(kickoff))
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        with direct_vm.expect_revert("betting_closed"):
            contract.place_bet(fixture_id, "HOME")

    def test_bet_below_min_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET - 1
        with direct_vm.expect_revert("below_min_bet"):
            contract.place_bet(fixture_id, "HOME")

    def test_unknown_outcome_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        with direct_vm.expect_revert("unknown_outcome"):
            contract.place_bet(fixture_id, "TIE")


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------

class TestResolve:
    def test_too_early_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.warp(_iso(kickoff + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        with direct_vm.expect_revert("too_early"):
            contract.resolve(fixture_id)

    def test_no_bets_rejected(self, direct_vm, direct_deploy, direct_alice, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        with direct_vm.expect_revert("no_bets"):
            contract.resolve(fixture_id)

    def test_wrong_bond_amount_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        mock_both_desks(direct_vm, fixture_id)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND - 1
        with direct_vm.expect_revert("wrong_bond_amount"):
            contract.resolve(fixture_id)

    def test_both_ft_match_decisive(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        verdict = _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie, home=2, away=1)
        assert verdict == "HOME"
        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "PENDING"
        assert fixture["code"] == "CLEAR"
        assert contract.get_scoreline(fixture_id) == {"home": 2, "away": 1, "status": "FT"}

    def test_score_conflict_inconclusive(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        mock_both_desks(direct_vm, fixture_id, home=2, away=1, home_b=2, away_b=2)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        verdict = contract.resolve(fixture_id)
        assert verdict == "INCONCLUSIVE"
        assert contract.get_fixture(fixture_id)["code"] == "CONFLICT"

    def test_one_live_inconclusive(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        mock_both_desks(direct_vm, fixture_id, status_a="LIVE")
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        verdict = contract.resolve(fixture_id)
        assert verdict == "INCONCLUSIVE"
        assert contract.get_fixture(fixture_id)["code"] == "LIVE"

    def test_postponed_inconclusive(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        mock_both_desks(direct_vm, fixture_id, status_a="POSTPONED", status_b="POSTPONED", home=None, away=None)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        verdict = contract.resolve(fixture_id)
        assert verdict == "INCONCLUSIVE"
        assert contract.get_fixture(fixture_id)["code"] == "POSTPONED"

    def test_same_scoreline_different_asof_still_decisive(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        """asof/raw payload timing may differ between desks; only the
        derived FT scoreline is compared."""
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "AWAY")
        url_a = lib.build_desk_url("desk_a", fixture_id)
        url_b = lib.build_desk_url("desk_b", fixture_id)
        direct_vm.mock_web(re.escape(url_a), {"body": json.dumps({"events": [{"strStatus": "Match Finished", "intHomeScore": "0", "intAwayScore": "3", "strTimestamp": "2030-01-01T20:00:00Z"}]}), "status": 200})
        direct_vm.mock_web(re.escape(url_b), {"body": json.dumps({"matchStatus": "FT", "homeGoals": 0, "awayGoals": 3, "lastUpdate": "2030-01-01T20:07:00Z"}), "status": 200})
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        verdict = contract.resolve(fixture_id)
        assert verdict == "AWAY"

    def test_latest_window_fallback_inconclusive(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_LATEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        verdict = contract.resolve(fixture_id)
        assert verdict == "INCONCLUSIVE"
        assert contract.get_fixture(fixture_id)["code"] == "WINDOW_EXPIRED"

    def test_already_resolved_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        with direct_vm.expect_revert("not_open"):
            contract.resolve(fixture_id)


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

class TestFinalize:
    def test_appeal_window_open_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        with direct_vm.expect_revert("appeal_open"):
            contract.finalize(fixture_id)

    def test_decisive_finalize_pays_fee_shares(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = 10 * lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + 1800 + 1))
        contract.finalize(fixture_id)
        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "FINALIZED"
        assert fixture["verdict"] == "HOME"

    def test_inconclusive_finalize_no_fee(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        mock_both_desks(direct_vm, fixture_id, status_a="LIVE")
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        contract.resolve(fixture_id)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + 1800 + 1))
        contract.finalize(fixture_id)
        assert contract.get_fixture(fixture_id)["state"] == "INCONCLUSIVE"

    def test_decisive_verdict_zero_stakers_on_winner_refunds_instead(
        self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_owner, direct_charlie
    ):
        """Bob bets HOME, owner bets AWAY -- nobody bets DRAW. The real
        match ends 1-1 (a genuine DRAW). Without this fix, finalize()
        would mark this FINALIZED and strand the whole pot: neither
        bettor's outcome matches the winner, so nobody could ever
        claim() it. It must settle INCONCLUSIVE (full refund) instead."""
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = 3 * lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.sender = direct_owner
        direct_vm.value = 5 * lib.MIN_BET
        contract.place_bet(fixture_id, "AWAY")

        verdict = _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie, home=1, away=1)
        assert verdict == "DRAW"
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + 1800 + 1))
        contract.finalize(fixture_id)

        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "INCONCLUSIVE"
        assert fixture["code"] == "NO_STAKERS_ON_WINNER"

        direct_vm.sender = direct_bob
        direct_vm.value = 0
        assert contract.claim(fixture_id) == 3 * lib.MIN_BET
        direct_vm.sender = direct_owner
        direct_vm.value = 0
        assert contract.claim(fixture_id) == 5 * lib.MIN_BET


# ---------------------------------------------------------------------------
# appeal / re_adjudicate / lapse_appeal
# ---------------------------------------------------------------------------

class TestAppealLifecycle:
    def test_appeal_by_non_party_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        stranger = create_address("stranger")
        direct_vm.sender = stranger
        direct_vm.value = lib.APPEAL_BOND_FLOOR
        with direct_vm.expect_revert("not_a_party"):
            contract.appeal(fixture_id, "SCORE")

    def test_appeal_wrong_bond_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        direct_vm.sender = direct_bob
        direct_vm.value = 1
        with direct_vm.expect_revert("wrong_bond_amount"):
            contract.appeal(fixture_id, "SCORE")

    def test_appeal_unknown_ground_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.APPEAL_BOND_FLOOR
        with direct_vm.expect_revert("unknown_ground"):
            contract.appeal(fixture_id, "VIBES")

    def test_appeal_then_re_adjudicate_reverses_verdict(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_owner, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "AWAY")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie, home=2, away=1)
        assert contract.get_fixture(fixture_id)["verdict"] == "HOME"

        direct_vm.sender = direct_bob
        direct_vm.value = lib.APPEAL_BOND_FLOOR
        contract.appeal(fixture_id, "SCORE")
        assert contract.get_fixture(fixture_id)["state"] == "APPEALED"

        # a corrected re-fetch now shows the true 1-2 scoreline -- clear
        # the prior mock_web registration first, since gltest's mock
        # matches in registration order (first match wins), not most
        # recent (see genlayer-test-toolchain memory).
        direct_vm.clear_mocks()
        mock_both_desks(direct_vm, fixture_id, home=1, away=2)
        direct_vm.sender = direct_owner
        direct_vm.value = lib.RESOLVE_BOND
        new_verdict = contract.re_adjudicate(fixture_id)
        assert new_verdict == "AWAY"
        assert contract.get_fixture(fixture_id)["state"] == "PENDING"

        # prior resolver (charlie) already got their bond back
        # automatically inside re_adjudicate, via a direct GEN transfer --
        # not through reclaim_bonds's flag (that flag now tracks the NEW
        # resolver, owner, whose bond is still outstanding). Confirm
        # charlie has no separate claim path left for it: reclaim_bonds
        # rejects here for an unrelated reason (the fixture is back in
        # PENDING, not yet terminal), not because there's nothing owed --
        # proving there is no double-payment path for the old bond.
        direct_vm.sender = direct_charlie
        direct_vm.value = 0
        with direct_vm.expect_revert("not_terminal"):
            contract.reclaim_bonds(fixture_id)

        # carry through to finalize: the NEW resolver (owner) can reclaim
        # their own bond afterward, proving the reset didn't strand it.
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + 1800 + 1))
        contract.finalize(fixture_id)
        direct_vm.sender = direct_owner
        direct_vm.value = 0
        owed = contract.reclaim_bonds(fixture_id)
        assert owed == lib.RESOLVE_BOND

    def test_lapse_appeal_restores_prior_verdict(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _resolve_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        # winning pool is exactly MIN_BET (bob's only bet); 50% of that
        # (0.5 GEN) exceeds APPEAL_BOND_FLOOR (0.05 GEN), so the real
        # required bond is the pool-based half, not the floor.
        bond = lib.appeal_bond_amount(lib.MIN_BET)
        direct_vm.sender = direct_bob
        direct_vm.value = bond
        contract.appeal(fixture_id, "SCORE")

        with direct_vm.expect_revert("appeal_not_stalled"):
            contract.lapse_appeal(fixture_id)

        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + lib.LAPSE_APPEAL_STALL + 1))
        contract.lapse_appeal(fixture_id)
        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "PENDING"
        assert fixture["verdict"] == "HOME"


# ---------------------------------------------------------------------------
# cancel_fixture / expire_fixture
# ---------------------------------------------------------------------------

class TestCancelExpire:
    def test_cancel_by_creator_zero_bets(self, direct_vm, direct_deploy, direct_alice):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_alice
        direct_vm.value = 0
        contract.cancel_fixture(fixture_id)
        assert contract.get_fixture(fixture_id)["state"] == "CANCELED"
        assert contract.get_fixture(fixture_id)["create_bond_returned"] is True

    def test_cancel_rejected_if_bets_exist(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.sender = direct_alice
        direct_vm.value = 0
        with direct_vm.expect_revert("bets_exist"):
            contract.cancel_fixture(fixture_id)

    def test_cancel_by_non_creator_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = 0
        with direct_vm.expect_revert("not_a_party"):
            contract.cancel_fixture(fixture_id)

    def test_expire_slashes_bond_on_zero_bets_at_kickoff(self, direct_vm, direct_deploy, direct_alice, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.warp(_iso(kickoff + 1))
        direct_vm.sender = direct_charlie  # permissionless
        direct_vm.value = 0
        contract.expire_fixture(fixture_id)
        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "EXPIRED"
        assert fixture["create_bond_slashed"] is True

    def test_expire_before_kickoff_rejected(self, direct_vm, direct_deploy, direct_alice):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_alice
        direct_vm.value = 0
        with direct_vm.expect_revert("kickoff_not_reached"):
            contract.expire_fixture(fixture_id)


# ---------------------------------------------------------------------------
# recover_refund
# ---------------------------------------------------------------------------

class TestRecoverRefund:
    def test_before_window_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.sender = direct_bob
        direct_vm.value = 0
        with direct_vm.expect_revert("recovery_window_not_reached"):
            contract.recover_refund(fixture_id)

    def test_after_7d_stall_recovers(self, direct_vm, direct_deploy, direct_alice, direct_bob):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.warp(_iso(kickoff + lib.RECOVER_REFUND_AFTER + 10))
        direct_vm.sender = direct_bob
        direct_vm.value = 0
        contract.recover_refund(fixture_id)
        fixture = contract.get_fixture(fixture_id)
        assert fixture["state"] == "INCONCLUSIVE"

        direct_vm.value = 0
        refund = contract.claim(fixture_id)
        assert refund == lib.MIN_BET


# ---------------------------------------------------------------------------
# claim / reclaim_bonds
# ---------------------------------------------------------------------------

def _finalize_decisive(direct_vm, contract, fixture_id, kickoff, resolver, home=2, away=1):
    _resolve_decisive(direct_vm, contract, fixture_id, kickoff, resolver, home=home, away=away)
    direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + 1800 + 1))
    contract.finalize(fixture_id)


class TestClaim:
    def test_pro_rata_and_dust(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_owner, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET + 1  # deliberately not evenly divisible
        contract.place_bet(fixture_id, "HOME")
        direct_vm.sender = direct_owner
        direct_vm.value = lib.MIN_BET + 2
        contract.place_bet(fixture_id, "HOME")
        _finalize_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)

        total_pool = contract.get_fixture(fixture_id)["total_pool"]
        fee_total, _, _ = lib.decisive_fee(total_pool)
        distributable = total_pool - fee_total

        direct_vm.sender = direct_bob
        direct_vm.value = 0
        p1 = contract.claim(fixture_id)
        direct_vm.sender = direct_owner
        direct_vm.value = 0
        p2 = contract.claim(fixture_id)
        assert p1 + p2 == distributable

    def test_loser_nothing_to_claim(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_owner, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        direct_vm.sender = direct_owner
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "AWAY")
        _finalize_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie, home=2, away=1)

        direct_vm.sender = direct_owner
        direct_vm.value = 0
        with direct_vm.expect_revert("nothing_to_claim"):
            contract.claim(fixture_id)

    def test_double_claim_rejected(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _finalize_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)
        direct_vm.sender = direct_bob
        direct_vm.value = 0
        contract.claim(fixture_id)
        with direct_vm.expect_revert("nothing_to_claim"):
            contract.claim(fixture_id)

    def test_inconclusive_full_refund_zero_fee(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = 7 * lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        mock_both_desks(direct_vm, fixture_id, status_a="POSTPONED", status_b="POSTPONED", home=None, away=None)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10))
        direct_vm.sender = direct_charlie
        direct_vm.value = lib.RESOLVE_BOND
        contract.resolve(fixture_id)
        direct_vm.warp(_iso(kickoff + lib.RESOLVE_EARLIEST_OFFSET + 10 + 1800 + 1))
        contract.finalize(fixture_id)

        direct_vm.sender = direct_bob
        direct_vm.value = 0
        refund = contract.claim(fixture_id)
        assert refund == 7 * lib.MIN_BET


class TestReclaimBonds:
    def test_create_bond_to_creator_after_finalize(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _finalize_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)

        direct_vm.sender = direct_alice
        direct_vm.value = 0
        owed = contract.reclaim_bonds(fixture_id)
        assert owed == lib.CREATE_BOND
        assert contract.get_fixture(fixture_id)["create_bond_returned"] is True

    def test_resolve_bond_to_resolver_after_finalize(self, direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_bob
        direct_vm.value = lib.MIN_BET
        contract.place_bet(fixture_id, "HOME")
        _finalize_decisive(direct_vm, contract, fixture_id, kickoff, direct_charlie)

        direct_vm.sender = direct_charlie
        direct_vm.value = 0
        owed = contract.reclaim_bonds(fixture_id)
        assert owed == lib.RESOLVE_BOND

    def test_before_terminal_rejected(self, direct_vm, direct_deploy, direct_alice):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        direct_vm.sender = direct_alice
        direct_vm.value = 0
        with direct_vm.expect_revert("not_terminal"):
            contract.reclaim_bonds(fixture_id)


# ---------------------------------------------------------------------------
# views / pagination
# ---------------------------------------------------------------------------

class TestViews:
    def test_get_board_paginates(self, direct_vm, direct_deploy, direct_alice):
        direct_vm.warp(_iso(ANCHOR_EPOCH))
        contract = _deploy(direct_deploy)
        direct_vm.sender = direct_alice
        for i in range(5):
            direct_vm.value = lib.CREATE_BOND
            contract.create_fixture(f"fx-{i}", "A", "B", ANCHOR_EPOCH + lib.MIN_LEAD + i)
        page1 = contract.get_board(0, 2, "")
        assert len(page1["rows"]) == 2
        page2 = contract.get_board(page1["next_cursor"], 2, "")
        assert len(page2["rows"]) == 2

    def test_get_board_state_filter(self, direct_vm, direct_deploy, direct_alice):
        contract, fixture_id, kickoff = _open_fixture(direct_vm, direct_deploy, direct_alice)
        board = contract.get_board(0, 50, "OPEN")
        assert any(r["fixture_id"] == fixture_id for r in board["rows"])
        board_none = contract.get_board(0, 50, "FINALIZED")
        assert board_none["rows"] == []

    def test_get_fixture_unknown_rejected(self, direct_deploy):
        contract = _deploy(direct_deploy)
        with pytest.raises(Exception):
            contract.get_fixture("nope")

    def test_get_registry_locked(self, direct_deploy):
        contract = _deploy(direct_deploy)
        registry = contract.get_registry()
        assert set(registry.keys()) == {"desk_a", "desk_b"}
        for desk in registry.values():
            assert desk["host"].startswith("https://")
