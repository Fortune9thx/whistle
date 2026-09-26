"""
Plain-pytest unit tests for contracts/whistle_lib.py -- zero genlayer
import, no GenVM sandbox. Covers the comparator/derivation invariants
that gltest direct-mode cannot exercise (run_nondet_default's mock only
ever invokes leader_fn, never validator_fn) -- see docs/architecture.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "contracts"))

import pytest

import whistle_lib as lib


# ---------------------------------------------------------------------------
# constitution validation
# ---------------------------------------------------------------------------

def _payload(**overrides):
    base = {
        "fixture_id": "ucl-2026-md1-001",
        "home": "Real Madrid",
        "away": "Bayern Munich",
        "kickoff_unix": 2_000_000_000,
    }
    base.update(overrides)
    return base


def test_validate_constitution_ok():
    lib.validate_constitution(_payload(), now_ts=1_999_000_000, open_count_for_creator=0)


def test_validate_constitution_below_min_lead():
    now_ts = _payload()["kickoff_unix"] - lib.MIN_LEAD + 1
    with pytest.raises(lib.WhistleValidationError) as exc:
        lib.validate_constitution(_payload(), now_ts=now_ts, open_count_for_creator=0)
    assert exc.value.code == "below_min_lead"


def test_validate_constitution_min_lead_boundary_ok():
    now_ts = _payload()["kickoff_unix"] - lib.MIN_LEAD
    lib.validate_constitution(_payload(), now_ts=now_ts, open_count_for_creator=0)


def test_validate_constitution_home_equals_away():
    with pytest.raises(lib.WhistleValidationError) as exc:
        lib.validate_constitution(_payload(away="Real Madrid"), now_ts=0, open_count_for_creator=0)
    assert exc.value.code == "home_equals_away"


def test_validate_constitution_creator_cap():
    with pytest.raises(lib.WhistleValidationError) as exc:
        lib.validate_constitution(_payload(), now_ts=0, open_count_for_creator=lib.MAX_OPEN_PER_CREATOR)
    assert exc.value.code == "creator_cap_reached"


def test_validate_constitution_missing_field():
    payload = _payload()
    del payload["kickoff_unix"]
    with pytest.raises(lib.WhistleValidationError) as exc:
        lib.validate_constitution(payload, now_ts=0, open_count_for_creator=0)
    assert exc.value.code == "missing_kickoff_unix"


# ---------------------------------------------------------------------------
# desk URL builders -- locked, no user URLs
# ---------------------------------------------------------------------------

def test_build_desk_url_locked_host():
    url_a = lib.build_desk_url("desk_a", "fx-1")
    url_b = lib.build_desk_url("desk_b", "fx-1")
    assert url_a.startswith(lib.PUBLISHER_REGISTRY["desk_a"]["host"])
    assert url_b.startswith(lib.PUBLISHER_REGISTRY["desk_b"]["host"])
    assert "fx-1" in url_a and "fx-1" in url_b


def test_build_desk_url_unknown_desk_rejected():
    with pytest.raises(ValueError):
        lib.build_desk_url("desk_z", "fx-1")


# ---------------------------------------------------------------------------
# per-desk parsing
# ---------------------------------------------------------------------------

def test_parse_desk_a_ft():
    raw = '{"events": [{"strStatus": "Match Finished", "intHomeScore": "2", "intAwayScore": "1", "strTimestamp": "t0"}]}'
    parsed = lib.parse_response_body("desk_a", raw)
    assert parsed == {"usable": True, "status": "FT", "home": 2, "away": 1, "asof": "t0"}


def test_parse_desk_b_ft():
    raw = '{"matchStatus": "FT", "homeGoals": 2, "awayGoals": 1, "lastUpdate": "t1"}'
    parsed = lib.parse_response_body("desk_b", raw)
    assert parsed == {"usable": True, "status": "FT", "home": 2, "away": 1, "asof": "t1"}


def test_parse_desk_a_live_unusable():
    raw = '{"events": [{"strStatus": "1H", "intHomeScore": "1", "intAwayScore": "0"}]}'
    parsed = lib.parse_response_body("desk_a", raw)
    assert parsed["usable"] is False
    assert parsed["status"] == "LIVE"


def test_parse_response_too_large():
    raw = '{"events": [' + "x" * (lib.MAX_RESPONSE_BYTES + 10) + "]}"
    parsed = lib.parse_response_body("desk_a", raw)
    assert parsed == {"usable": False, "reason": "response_too_large"}


def test_parse_response_malformed_json():
    parsed = lib.parse_response_body("desk_a", "not json{{{")
    assert parsed == {"usable": False, "reason": "decode_fail"}


def test_parse_response_missing_body():
    parsed = lib.parse_response_body("desk_a", None)
    assert parsed == {"usable": False, "reason": "missing_body"}


# ---------------------------------------------------------------------------
# 1X2 derivation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "home,away,expected",
    [(2, 1, "HOME"), (0, 3, "AWAY"), (1, 1, "DRAW"), (0, 0, "DRAW")],
)
def test_derive_1x2(home, away, expected):
    assert lib.derive_1x2(home, away) == expected


# ---------------------------------------------------------------------------
# evaluate_sources -- the core two-publisher comparator
# ---------------------------------------------------------------------------

def _src(status="FT", home=2, away=1):
    return {"usable": status == "FT", "status": status, "home": home, "away": away, "asof": 0}


def test_both_ft_match_clear():
    sources = {"desk_a": _src(), "desk_b": _src()}
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "CLEAR"
    assert scoreline == {"home": 2, "away": 1, "status": "FT"}


def test_same_scoreline_different_asof_still_accepts():
    sources = {
        "desk_a": {**_src(), "asof": "2026-09-26T20:00:00Z"},
        "desk_b": {**_src(), "asof": "2026-09-26T20:00:07Z"},
    }
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "CLEAR"
    assert scoreline == {"home": 2, "away": 1, "status": "FT"}


def test_score_conflict_refund():
    sources = {"desk_a": _src(home=2, away=1), "desk_b": _src(home=2, away=2)}
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "CONFLICT"
    assert scoreline is None


def test_one_live_refund():
    sources = {"desk_a": _src(status="LIVE", home=1, away=0), "desk_b": _src()}
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "LIVE"
    assert scoreline is None


def test_postponed_refund():
    sources = {"desk_a": _src(status="POSTPONED", home=0, away=0), "desk_b": _src(status="POSTPONED", home=0, away=0)}
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "POSTPONED"
    assert scoreline is None


def test_abandoned_refund():
    sources = {"desk_a": _src(status="ABANDONED", home=0, away=0), "desk_b": _src()}
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "ABANDONED"
    assert scoreline is None


def test_missing_source_refund():
    code, scoreline = lib.evaluate_sources({"desk_a": _src()})
    assert code == "MISSING"
    assert scoreline is None


def test_usable_flag_never_trusted_blindly():
    """A desk claiming usable=True while status is not FT is still
    treated as unusable -- code recomputes usability itself."""
    sources = {"desk_a": {"usable": True, "status": "LIVE", "home": 1, "away": 0, "asof": 0}, "desk_b": _src()}
    code, scoreline = lib.evaluate_sources(sources)
    assert code == "LIVE"
    assert scoreline is None


# ---------------------------------------------------------------------------
# envelope construction + self-consistency + the leader/validator comparator
# ---------------------------------------------------------------------------

def test_build_envelope_clear():
    sources = {"desk_a": _src(), "desk_b": _src()}
    env = lib.build_envelope("fx-1", sources)
    assert env["code"] == "CLEAR"
    assert env["verdict_1x2"] == "HOME"
    assert env["scoreline"] == {"home": 2, "away": 1, "status": "FT"}


def test_build_envelope_inconclusive():
    sources = {"desk_a": _src(status="LIVE"), "desk_b": _src()}
    env = lib.build_envelope("fx-1", sources)
    assert env["code"] == "LIVE"
    assert env["verdict_1x2"] == "INCONCLUSIVE"
    assert env["scoreline"] is None


def test_is_well_formed_rejects_lying_leader_verdict():
    """A leader that reports scoreline 1-2 (AWAY) but a hand-tampered
    verdict_1x2 of 'HOME' is rejected outright, purely by recomputing
    verdict from the envelope's own claimed scoreline -- no second fetch
    needed to catch this."""
    sources = {"desk_a": _src(home=1, away=2), "desk_b": _src(home=1, away=2)}
    honest = lib.build_envelope("fx-1", sources)
    assert honest["verdict_1x2"] == "AWAY"

    lying = dict(honest)
    lying["verdict_1x2"] = "HOME"
    assert lib.is_well_formed_envelope(lying, "fx-1") is False
    assert lib.is_well_formed_envelope(honest, "fx-1") is True


def test_is_well_formed_rejects_lying_leader_code():
    sources = {"desk_a": _src(home=2, away=2), "desk_b": _src(home=2, away=1)}  # CONFLICT
    honest = lib.build_envelope("fx-1", sources)
    assert honest["code"] == "CONFLICT"

    lying = dict(honest)
    lying["code"] = "CLEAR"
    lying["scoreline"] = {"home": 2, "away": 1, "status": "FT"}
    lying["verdict_1x2"] = "HOME"
    assert lib.is_well_formed_envelope(lying, "fx-1") is False


def test_is_well_formed_rejects_wrong_fixture_id():
    sources = {"desk_a": _src(), "desk_b": _src()}
    env = lib.build_envelope("fx-1", sources)
    assert lib.is_well_formed_envelope(env, "fx-OTHER") is False


def test_compare_envelopes_accepts_matching_independent_fetch():
    sources_leader = {"desk_a": {**_src(), "asof": "t0"}, "desk_b": {**_src(), "asof": "t0"}}
    sources_validator = {"desk_a": {**_src(), "asof": "t5"}, "desk_b": {**_src(), "asof": "t6"}}
    leader = lib.build_envelope("fx-1", sources_leader)
    mine = lib.build_envelope("fx-1", sources_validator)
    assert lib.compare_envelopes(mine, leader, "fx-1") is True


def test_compare_envelopes_rejects_lying_leader():
    """The leader fabricates a HOME verdict; an honest independent
    re-fetch (matching the true AWAY scoreline) disagrees -> reject,
    no pot move."""
    true_sources = {"desk_a": _src(home=0, away=1), "desk_b": _src(home=0, away=1)}
    honest = lib.build_envelope("fx-1", true_sources)

    lying = dict(honest)
    lying["verdict_1x2"] = "HOME"

    assert lib.compare_envelopes(honest, lying, "fx-1") is False


def test_compare_envelopes_rejects_disagreeing_independent_fetches():
    """Leader's fetch says CLEAR/HOME; validator's own independent fetch
    (real timing race, or a genuinely different observation) says
    LIVE/INCONCLUSIVE -- must reject rather than silently pick one."""
    leader_sources = {"desk_a": _src(), "desk_b": _src()}
    validator_sources = {"desk_a": _src(status="LIVE"), "desk_b": _src()}
    leader = lib.build_envelope("fx-1", leader_sources)
    mine = lib.build_envelope("fx-1", validator_sources)
    assert lib.compare_envelopes(mine, leader, "fx-1") is False


# ---------------------------------------------------------------------------
# fee / bond / payout math
# ---------------------------------------------------------------------------

def test_decisive_fee_split():
    fee_total, resolver_share, treasury_share = lib.decisive_fee(10_000 * 10**18)
    assert fee_total == 200 * 10**18  # 2%
    assert resolver_share + treasury_share == fee_total
    assert resolver_share == treasury_share  # even split, even fee_total


def test_decisive_fee_odd_remainder_goes_to_treasury():
    fee_total, resolver_share, treasury_share = lib.decisive_fee(101)
    assert fee_total == 2  # 101 * 200 // 10000 == 2
    assert resolver_share == 1
    assert treasury_share == 1


def test_appeal_bond_floor():
    assert lib.appeal_bond_amount(0) == lib.APPEAL_BOND_FLOOR
    assert lib.appeal_bond_amount(10**16) == lib.APPEAL_BOND_FLOOR  # half < floor


def test_appeal_bond_half_of_pool():
    pool = 10 * 10**18
    assert lib.appeal_bond_amount(pool) == pool // 2


def test_claim_payout_prorata():
    payout = lib.compute_claim_payout(
        my_stake=3 * 10**18,
        winning_pool_total=10 * 10**18,
        distributable=9_800 * 10**15,  # 9.8 GEN after 2% fee off a 10 GEN pot proxy
        claimed_stake_before=0,
        claimed_amount_before=0,
    )
    assert payout == (3 * 10**18 * 9_800 * 10**15) // (10 * 10**18)


def test_claim_payout_last_claimant_gets_dust():
    winning_pool_total = 3  # deliberately indivisible
    distributable = 10
    # two prior claimants of 1 wei stake each already claimed their floor share
    first = lib.compute_claim_payout(1, winning_pool_total, distributable, 0, 0)
    second = lib.compute_claim_payout(1, winning_pool_total, distributable, 1, first)
    third = lib.compute_claim_payout(1, winning_pool_total, distributable, 2, first + second)
    assert first + second + third == distributable  # no dust stranded
    assert third == distributable - (first + second)  # last claimant absorbs the remainder


def test_claim_payout_zero_winning_pool_raises():
    with pytest.raises(ValueError):
        lib.compute_claim_payout(1, 0, 10, 0, 0)


# ---------------------------------------------------------------------------
# pagination
# ---------------------------------------------------------------------------

def test_paginate_basic():
    ids = [str(i) for i in range(5)]
    page, next_cursor = lib.paginate(ids, cursor=0, limit=2)
    assert page == ["0", "1"]
    assert next_cursor == 2


def test_paginate_last_page_no_next_cursor():
    ids = [str(i) for i in range(5)]
    page, next_cursor = lib.paginate(ids, cursor=4, limit=2)
    assert page == ["4"]
    assert next_cursor == 0


def test_paginate_oversized_limit_capped():
    ids = [str(i) for i in range(3)]
    page, next_cursor = lib.paginate(ids, cursor=0, limit=lib.MAX_PAGE_SIZE + 100)
    assert page == ids
    assert next_cursor == 0


# ---------------------------------------------------------------------------
# appeal grounds
# ---------------------------------------------------------------------------

def test_valid_appeal_grounds():
    assert lib.VALID_APPEAL_GROUNDS == ("SCORE", "STATUS", "FIXTURE", "REVISED")
