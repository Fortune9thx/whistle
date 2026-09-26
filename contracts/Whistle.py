# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
#
# WHISTLE -- settles one object on-chain: the full-time 90-minute
# scoreline of a locked fixture, from two locked publisher desks. See
# README.md for the steward brief and docs/ for the state machine and
# threat model.
#
# NOTE ON THE DEPENDS HASH: pinned to the same runner confirmed
# lint/gltest-working and live-deployed by prior projects on this account
# (py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng, SDK
# generation v0.6.0-rc6). See docs/architecture.md for the toolchain
# version table.
#
# Two deliberate, documented deviations from the original build brief,
# both toolchain-forced (see docs/architecture.md):
# - `raise gl.vm.UserError(...)`, not `gl.vm.UserError.immediate(...)`:
#   gltest direct-mode's mock implements `.immediate()` as a bare
#   `assert False`, discarding the error string entirely, so no local
#   test can assert on *which* guard fired. `raise UserError(...)` is
#   the same real, live GenVM user-error path with the message intact.
# - `gl.vm.run_nondet`, not `gl.vm.run_nondet_default`: the latest
#   available genvm-linter (0.11.1rc2) doesn't yet recognize
#   run_nondet_default as an equivalence-principle call.
import json
from datetime import datetime, timezone

import genlayer as gl
from genlayer.storage import DynArray, TreeMap
from genlayer.types import Address, u256

from whistle_lib import (
    CREATE_BOND,
    DESK_IDS,
    LAPSE_APPEAL_STALL,
    MAX_OPEN_PER_CREATOR,
    MAX_PAGE_SIZE,
    MIN_BET,
    MIN_LEAD,
    OUTCOMES,
    PUBLISHER_REGISTRY,
    RECOVER_REFUND_AFTER,
    RESOLVE_BOND,
    RESOLVE_EARLIEST_OFFSET,
    RESOLVE_LATEST_OFFSET,
    VALID_APPEAL_GROUNDS,
    WhistleValidationError,
    appeal_bond_amount,
    build_desk_url,
    build_envelope,
    compare_envelopes,
    compute_claim_payout,
    constitution_view,
    decisive_fee,
    get_constitution_dict,
    paginate,
    parse_response_body,
    validate_constitution,
)

APPEAL_WINDOW = 1800  # 30 min -- not spec-numbered; a deliberate, documented default (see docs/architecture.md)


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


class EventFixtureCreated(gl.chain.Event):
    def __init__(self, fixture_id: str, creator: Address, kickoff_unix: u256, /): ...


class EventBetPlaced(gl.chain.Event):
    def __init__(self, fixture_id: str, bettor: Address, outcome: str, /): ...


class EventResolved(gl.chain.Event):
    def __init__(self, fixture_id: str, verdict: str, code: str, /): ...


class EventFinalized(gl.chain.Event):
    def __init__(self, fixture_id: str, verdict: str, /): ...


class EventAppealed(gl.chain.Event):
    def __init__(self, fixture_id: str, appellant: Address, ground: str, /): ...


class EventLapsedAppeal(gl.chain.Event):
    def __init__(self, fixture_id: str, /): ...


class EventCanceled(gl.chain.Event):
    def __init__(self, fixture_id: str, /): ...


class EventExpired(gl.chain.Event):
    def __init__(self, fixture_id: str, /): ...


class EventRecovered(gl.chain.Event):
    def __init__(self, fixture_id: str, /): ...


class Claimed(gl.chain.Event):
    def __init__(self, fixture_id: str, claimant: Address, amount: u256, /): ...


class Whistle(gl.contract.Contract):
    treasury: Address

    fixture_home: TreeMap[str, str]
    fixture_away: TreeMap[str, str]
    fixture_kickoff: TreeMap[str, u256]
    fixture_creator: TreeMap[str, str]
    fixture_state: TreeMap[str, str]
    fixture_verdict: TreeMap[str, str]
    fixture_code: TreeMap[str, str]
    fixture_scoreline_json: TreeMap[str, str]
    fixture_evidence_json: TreeMap[str, str]
    fixture_appeal_json: TreeMap[str, str]
    fixture_resolver: TreeMap[str, str]
    fixture_total_pool: TreeMap[str, u256]
    fixture_claimed_stake: TreeMap[str, u256]
    fixture_claimed_amount: TreeMap[str, u256]
    fixture_create_bond_returned: TreeMap[str, u256]
    fixture_create_bond_slashed: TreeMap[str, u256]
    fixture_resolve_bond_returned: TreeMap[str, u256]
    fixture_last_state_change: TreeMap[str, u256]

    pool_by_outcome: TreeMap[str, u256]
    position_amount: TreeMap[str, u256]
    position_outcome: TreeMap[str, str]
    position_claimed: TreeMap[str, u256]

    creator_open_count: TreeMap[str, u256]
    user_fixture_ids: TreeMap[str, DynArray[str]]
    all_fixture_ids: DynArray[str]

    def __init__(self, treasury: str):
        self.treasury = Address(treasury)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _now_unix(self) -> int:
        # datetime.now(timezone.utc) is pinned to the transaction's own
        # deterministic datetime on GenVM -- see docs/architecture.md.
        return int(datetime.now(timezone.utc).timestamp())

    def _sender(self) -> str:
        return gl.message.sender_address.as_hex

    def _require_exists(self, fixture_id: str) -> None:
        if fixture_id not in self.fixture_state:
            raise gl.vm.UserError("fixture_not_found")

    def _fixture_view(self, fixture_id: str) -> dict:
        kickoff = int(self.fixture_kickoff[fixture_id])
        pools = {o: int(self.pool_by_outcome.get(f"{fixture_id}:{o}", u256(0))) for o in OUTCOMES}
        appeal_raw = self.fixture_appeal_json.get(fixture_id, "")
        now = self._now_unix()
        state = self.fixture_state[fixture_id]
        return {
            "fixture_id": fixture_id,
            "competition": "UCL_LP",
            "home": self.fixture_home[fixture_id],
            "away": self.fixture_away[fixture_id],
            "kickoff_unix": kickoff,
            "creator": self.fixture_creator[fixture_id],
            "state": state,
            "locked": state == "OPEN" and now >= kickoff,
            "verdict": self.fixture_verdict.get(fixture_id, "") or None,
            "code": self.fixture_code.get(fixture_id, "") or None,
            "total_pool": int(self.fixture_total_pool[fixture_id]),
            "pool_by_outcome": pools,
            "resolver": self.fixture_resolver.get(fixture_id, "") or None,
            "appeal": json.loads(appeal_raw) if appeal_raw else None,
            "last_state_change_at": int(self.fixture_last_state_change[fixture_id]),
            "create_bond_returned": bool(int(self.fixture_create_bond_returned[fixture_id])),
            "create_bond_slashed": bool(int(self.fixture_create_bond_slashed[fixture_id])),
            "resolve_bond_returned": bool(int(self.fixture_resolve_bond_returned[fixture_id])),
        }

    # ------------------------------------------------------------------
    # create_fixture
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def create_fixture(self, fixture_id: str, home: str, away: str, kickoff_unix: u256) -> str:
        """Creates a new fixture. Attached GEN must equal CREATE_BOND
        exactly -- no stake is required from the creator. `fixture_id`
        must be unique and is the same identifier both locked publisher
        desks resolve the match by."""
        if fixture_id in self.fixture_state:
            raise gl.vm.UserError("duplicate_fixture")

        creator = self._sender()
        now_ts = self._now_unix()
        open_count = int(self.creator_open_count.get(creator, u256(0)))
        payload = {"fixture_id": fixture_id, "home": home, "away": away, "kickoff_unix": int(kickoff_unix)}
        try:
            validate_constitution(payload, now_ts=now_ts, open_count_for_creator=open_count)
        except WhistleValidationError as exc:
            raise gl.vm.UserError(exc.code)

        if int(gl.message.value) != CREATE_BOND:
            raise gl.vm.UserError("wrong_bond_amount")

        self.fixture_home[fixture_id] = home
        self.fixture_away[fixture_id] = away
        self.fixture_kickoff[fixture_id] = kickoff_unix
        self.fixture_creator[fixture_id] = creator
        self.fixture_state[fixture_id] = "OPEN"
        self.fixture_verdict[fixture_id] = ""
        self.fixture_code[fixture_id] = ""
        self.fixture_scoreline_json[fixture_id] = ""
        self.fixture_evidence_json[fixture_id] = ""
        self.fixture_appeal_json[fixture_id] = ""
        self.fixture_resolver[fixture_id] = ""
        self.fixture_total_pool[fixture_id] = u256(0)
        self.fixture_claimed_stake[fixture_id] = u256(0)
        self.fixture_claimed_amount[fixture_id] = u256(0)
        self.fixture_create_bond_returned[fixture_id] = u256(0)
        self.fixture_create_bond_slashed[fixture_id] = u256(0)
        self.fixture_resolve_bond_returned[fixture_id] = u256(0)
        self.fixture_last_state_change[fixture_id] = u256(now_ts)

        self.creator_open_count[creator] = u256(open_count + 1)
        self.all_fixture_ids.append(fixture_id)

        EventFixtureCreated(fixture_id, gl.message.sender_address, kickoff_unix).emit()
        return fixture_id

    # ------------------------------------------------------------------
    # place_bet
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def place_bet(self, fixture_id: str, outcome: str) -> str:
        self._require_exists(fixture_id)
        if outcome not in OUTCOMES:
            raise gl.vm.UserError("unknown_outcome")
        if self.fixture_state[fixture_id] != "OPEN":
            raise gl.vm.UserError("betting_closed")
        kickoff = int(self.fixture_kickoff[fixture_id])
        if self._now_unix() >= kickoff:
            raise gl.vm.UserError("betting_closed")
        if int(gl.message.value) < MIN_BET:
            raise gl.vm.UserError("below_min_bet")

        bettor = self._sender()
        pos_key = f"{fixture_id}:{bettor}"
        existing = self.position_outcome.get(pos_key, "")
        if existing != "" and existing != outcome:
            raise gl.vm.UserError("side_locked")

        amount = int(gl.message.value)
        self.position_amount[pos_key] = u256(int(self.position_amount.get(pos_key, u256(0))) + amount)
        self.position_outcome[pos_key] = outcome

        pool_key = f"{fixture_id}:{outcome}"
        self.pool_by_outcome[pool_key] = u256(int(self.pool_by_outcome.get(pool_key, u256(0))) + amount)
        self.fixture_total_pool[fixture_id] = u256(int(self.fixture_total_pool[fixture_id]) + amount)

        if existing == "":
            self.user_fixture_ids.get_or_insert_default(bettor).append(fixture_id)

        EventBetPlaced(fixture_id, gl.message.sender_address, outcome).emit()
        return "ok"

    # ------------------------------------------------------------------
    # resolve / re_adjudicate (shared core)
    # ------------------------------------------------------------------
    def _resolve_core(self, fixture_id: str, resolver: str) -> str:
        kickoff = int(self.fixture_kickoff[fixture_id])
        now_ts = self._now_unix()

        if now_ts >= kickoff + RESOLVE_LATEST_OFFSET:
            verdict, code, scoreline = "INCONCLUSIVE", "WINDOW_EXPIRED", None
        else:
            fixture_id_local = fixture_id

            def leader_fn() -> str:
                sources_raw = {}
                for desk in DESK_IDS:
                    url = build_desk_url(desk, fixture_id_local)
                    try:
                        resp = gl.nondet.web.get(url)
                        status = getattr(resp, "status", 200)
                        body = getattr(resp, "body", resp)
                        raw = body.decode("utf-8", errors="ignore") if isinstance(body, (bytes, bytearray)) else body
                        if status != 200:
                            sources_raw[desk] = {"usable": False, "status": "UNKNOWN", "home": None, "away": None, "asof": 0}
                            continue
                    except Exception:
                        sources_raw[desk] = {"usable": False, "status": "UNKNOWN", "home": None, "away": None, "asof": 0}
                        continue
                    sources_raw[desk] = parse_response_body(desk, raw)
                envelope = build_envelope(fixture_id_local, sources_raw)
                return json.dumps(envelope)

            def validator_fn(leader_result) -> bool:
                try:
                    leader_env = json.loads(str(leader_result.calldata))
                except (AttributeError, ValueError, TypeError):
                    return False
                my_raw = leader_fn()
                try:
                    my_env = json.loads(my_raw)
                except (ValueError, TypeError):
                    return False
                return compare_envelopes(my_env, leader_env, fixture_id_local)

            # run_nondet, not run_nondet_default: the latest genvm-linter
            # (0.11.1rc2) doesn't yet recognize run_nondet_default as an
            # equivalence-principle call and flags it as unreachable
            # nondet (E010). See docs/architecture.md.
            raw_envelope = gl.vm.run_nondet(leader_fn, validator_fn)
            try:
                envelope = json.loads(str(raw_envelope))
            except (ValueError, TypeError):
                envelope = {"fixture_id": fixture_id, "sources": {}, "scoreline": None, "verdict_1x2": "INCONCLUSIVE", "code": "MALFORMED"}

            verdict = envelope.get("verdict_1x2", "INCONCLUSIVE")
            code = envelope.get("code", "MALFORMED")
            scoreline = envelope.get("scoreline")

        self.fixture_verdict[fixture_id] = verdict
        self.fixture_code[fixture_id] = code
        self.fixture_scoreline_json[fixture_id] = json.dumps(scoreline) if scoreline else ""
        self.fixture_resolver[fixture_id] = resolver
        self.fixture_state[fixture_id] = "PENDING"
        self.fixture_last_state_change[fixture_id] = u256(now_ts)
        EventResolved(fixture_id, verdict, code).emit()
        return verdict

    @gl.public.write.payable
    def resolve(self, fixture_id: str) -> str:
        """Runs the two-publisher equivalence check once the fixture's
        earliest-resolve offset has passed. Attached GEN must equal
        RESOLVE_BOND exactly."""
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "OPEN":
            raise gl.vm.UserError("not_open")
        if int(self.fixture_total_pool[fixture_id]) == 0:
            raise gl.vm.UserError("no_bets")
        kickoff = int(self.fixture_kickoff[fixture_id])
        now_ts = self._now_unix()
        if now_ts < kickoff + RESOLVE_EARLIEST_OFFSET:
            raise gl.vm.UserError("too_early")
        if int(gl.message.value) != RESOLVE_BOND:
            raise gl.vm.UserError("wrong_bond_amount")

        return self._resolve_core(fixture_id, self._sender())

    # ------------------------------------------------------------------
    # appeal / re_adjudicate / lapse_appeal
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def appeal(self, fixture_id: str, ground: str) -> None:
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "PENDING":
            raise gl.vm.UserError("not_pending")
        if ground not in VALID_APPEAL_GROUNDS:
            raise gl.vm.UserError("unknown_ground")
        now_ts = self._now_unix()
        opened_at = int(self.fixture_last_state_change[fixture_id])
        if now_ts >= opened_at + APPEAL_WINDOW:
            raise gl.vm.UserError("appeal_closed")

        sender = self._sender()
        pos_key = f"{fixture_id}:{sender}"
        if int(self.position_amount.get(pos_key, u256(0))) == 0:
            raise gl.vm.UserError("not_a_party")

        verdict = self.fixture_verdict[fixture_id]
        winning_pool = int(self.pool_by_outcome.get(f"{fixture_id}:{verdict}", u256(0))) if verdict in OUTCOMES else 0
        bond = appeal_bond_amount(winning_pool)
        if int(gl.message.value) != bond:
            raise gl.vm.UserError("wrong_bond_amount")

        appeal_rec = {
            "appellant": sender,
            "ground": ground,
            "bond": bond,
            "opened_at": now_ts,
            "prior_verdict": verdict,
            "prior_code": self.fixture_code[fixture_id],
        }
        self.fixture_appeal_json[fixture_id] = json.dumps(appeal_rec)
        self.fixture_state[fixture_id] = "APPEALED"
        self.fixture_last_state_change[fixture_id] = u256(now_ts)
        EventAppealed(fixture_id, gl.message.sender_address, ground).emit()

    @gl.public.write.payable
    def re_adjudicate(self, fixture_id: str) -> str:
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "APPEALED":
            raise gl.vm.UserError("not_appealed")
        if int(gl.message.value) != RESOLVE_BOND:
            raise gl.vm.UserError("wrong_bond_amount")

        prior_resolver = self.fixture_resolver.get(fixture_id, "")
        if prior_resolver and not bool(int(self.fixture_resolve_bond_returned.get(fixture_id, u256(0)))):
            self.fixture_resolve_bond_returned[fixture_id] = u256(1)
            _Recipient(Address(prior_resolver)).emit_transfer(value=u256(RESOLVE_BOND))

        self.fixture_resolve_bond_returned[fixture_id] = u256(0)
        return self._resolve_core(fixture_id, self._sender())

    @gl.public.write
    def lapse_appeal(self, fixture_id: str) -> None:
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "APPEALED":
            raise gl.vm.UserError("not_appealed")
        appeal_raw = self.fixture_appeal_json[fixture_id]
        appeal_rec = json.loads(appeal_raw)
        now_ts = self._now_unix()
        if now_ts < appeal_rec["opened_at"] + LAPSE_APPEAL_STALL:
            raise gl.vm.UserError("appeal_not_stalled")

        self.fixture_verdict[fixture_id] = appeal_rec["prior_verdict"]
        self.fixture_code[fixture_id] = appeal_rec["prior_code"]
        _Recipient(self.treasury).emit_transfer(value=u256(appeal_rec["bond"]))
        self.fixture_appeal_json[fixture_id] = ""
        self.fixture_state[fixture_id] = "PENDING"
        self.fixture_last_state_change[fixture_id] = u256(now_ts)
        EventLapsedAppeal(fixture_id).emit()

    # ------------------------------------------------------------------
    # finalize
    # ------------------------------------------------------------------
    @gl.public.write
    def finalize(self, fixture_id: str) -> None:
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "PENDING":
            raise gl.vm.UserError("not_pending")
        now_ts = self._now_unix()
        opened_at = int(self.fixture_last_state_change[fixture_id])
        if now_ts < opened_at + APPEAL_WINDOW:
            raise gl.vm.UserError("appeal_open")

        verdict = self.fixture_verdict[fixture_id]
        total_pool = int(self.fixture_total_pool[fixture_id])

        if verdict in OUTCOMES:
            fee_total, resolver_share, treasury_share = decisive_fee(total_pool)
            resolver = self.fixture_resolver.get(fixture_id, "")
            if resolver_share > 0 and resolver:
                _Recipient(Address(resolver)).emit_transfer(value=u256(resolver_share))
            if treasury_share > 0:
                _Recipient(self.treasury).emit_transfer(value=u256(treasury_share))
            self.fixture_state[fixture_id] = "FINALIZED"
        else:
            self.fixture_state[fixture_id] = "INCONCLUSIVE"

        self.fixture_last_state_change[fixture_id] = u256(now_ts)
        creator = self.fixture_creator[fixture_id]
        cur = int(self.creator_open_count.get(creator, u256(0)))
        if cur > 0:
            self.creator_open_count[creator] = u256(cur - 1)
        EventFinalized(fixture_id, verdict or "INCONCLUSIVE").emit()

    # ------------------------------------------------------------------
    # cancel_fixture / expire_fixture
    # ------------------------------------------------------------------
    @gl.public.write
    def cancel_fixture(self, fixture_id: str) -> None:
        """Creator-only voluntary withdrawal, only while OPEN with zero
        bets placed. Full CREATE_BOND refund -- no slash."""
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "OPEN":
            raise gl.vm.UserError("not_open")
        if self._sender() != self.fixture_creator[fixture_id]:
            raise gl.vm.UserError("not_a_party")
        if int(self.fixture_total_pool[fixture_id]) != 0:
            raise gl.vm.UserError("bets_exist")

        self.fixture_state[fixture_id] = "CANCELED"
        self.fixture_create_bond_returned[fixture_id] = u256(1)
        self.fixture_last_state_change[fixture_id] = u256(self._now_unix())
        creator = self.fixture_creator[fixture_id]
        cur = int(self.creator_open_count.get(creator, u256(0)))
        if cur > 0:
            self.creator_open_count[creator] = u256(cur - 1)
        _Recipient(gl.message.sender_address).emit_transfer(value=u256(CREATE_BOND))
        EventCanceled(fixture_id).emit()

    @gl.public.write
    def expire_fixture(self, fixture_id: str) -> None:
        """Anyone may expire an OPEN fixture once kickoff has passed with
        zero bets ever placed. Slashes CREATE_BOND to treasury."""
        self._require_exists(fixture_id)
        if self.fixture_state[fixture_id] != "OPEN":
            raise gl.vm.UserError("not_open")
        kickoff = int(self.fixture_kickoff[fixture_id])
        if self._now_unix() < kickoff:
            raise gl.vm.UserError("kickoff_not_reached")
        if int(self.fixture_total_pool[fixture_id]) != 0:
            raise gl.vm.UserError("bets_exist")

        self.fixture_state[fixture_id] = "EXPIRED"
        self.fixture_create_bond_slashed[fixture_id] = u256(1)
        self.fixture_last_state_change[fixture_id] = u256(self._now_unix())
        creator = self.fixture_creator[fixture_id]
        cur = int(self.creator_open_count.get(creator, u256(0)))
        if cur > 0:
            self.creator_open_count[creator] = u256(cur - 1)
        _Recipient(self.treasury).emit_transfer(value=u256(CREATE_BOND))
        EventExpired(fixture_id).emit()

    # ------------------------------------------------------------------
    # recover_refund (escape hatch, 7d stall)
    # ------------------------------------------------------------------
    @gl.public.write
    def recover_refund(self, fixture_id: str) -> None:
        self._require_exists(fixture_id)
        state = self.fixture_state[fixture_id]
        if state not in ("OPEN", "PENDING", "APPEALED"):
            raise gl.vm.UserError("not_pending")
        if int(self.fixture_total_pool[fixture_id]) == 0:
            raise gl.vm.UserError("nothing_to_claim")
        kickoff = int(self.fixture_kickoff[fixture_id])
        now_ts = self._now_unix()
        if now_ts < kickoff + RECOVER_REFUND_AFTER:
            raise gl.vm.UserError("recovery_window_not_reached")

        appeal_raw = self.fixture_appeal_json.get(fixture_id, "")
        if appeal_raw:
            appeal_rec = json.loads(appeal_raw)
            _Recipient(Address(appeal_rec["appellant"])).emit_transfer(value=u256(appeal_rec["bond"]))
            self.fixture_appeal_json[fixture_id] = ""

        self.fixture_state[fixture_id] = "INCONCLUSIVE"
        self.fixture_verdict[fixture_id] = "INCONCLUSIVE"
        self.fixture_code[fixture_id] = "RECOVERED"
        self.fixture_last_state_change[fixture_id] = u256(now_ts)
        creator = self.fixture_creator[fixture_id]
        cur = int(self.creator_open_count.get(creator, u256(0)))
        if cur > 0:
            self.creator_open_count[creator] = u256(cur - 1)
        EventRecovered(fixture_id).emit()

    # ------------------------------------------------------------------
    # reclaim_bonds
    # ------------------------------------------------------------------
    @gl.public.write
    def reclaim_bonds(self, fixture_id: str) -> u256:
        self._require_exists(fixture_id)
        state = self.fixture_state[fixture_id]
        if state not in ("FINALIZED", "INCONCLUSIVE"):
            raise gl.vm.UserError("not_terminal")

        caller = self._sender()
        creator = self.fixture_creator[fixture_id]
        resolver = self.fixture_resolver.get(fixture_id, "")
        owed = 0
        did_something = False

        if not bool(int(self.fixture_create_bond_returned[fixture_id])) and caller == creator:
            self.fixture_create_bond_returned[fixture_id] = u256(1)
            owed += CREATE_BOND
            did_something = True

        if resolver and caller == resolver and not bool(int(self.fixture_resolve_bond_returned.get(fixture_id, u256(0)))):
            self.fixture_resolve_bond_returned[fixture_id] = u256(1)
            owed += RESOLVE_BOND
            did_something = True

        if not did_something:
            raise gl.vm.UserError("nothing_to_claim")

        if owed > 0:
            _Recipient(gl.message.sender_address).emit_transfer(value=u256(owed))
        return u256(owed)

    # ------------------------------------------------------------------
    # claim -- the ONLY method that pays out a bettor position
    # ------------------------------------------------------------------
    @gl.public.write
    def claim(self, fixture_id: str) -> u256:
        self._require_exists(fixture_id)
        state = self.fixture_state[fixture_id]
        if state not in ("FINALIZED", "INCONCLUSIVE"):
            raise gl.vm.UserError("nothing_to_claim")

        claimant = self._sender()
        pos_key = f"{fixture_id}:{claimant}"
        my_outcome = self.position_outcome.get(pos_key, "")
        my_stake = int(self.position_amount.get(pos_key, u256(0)))
        already = int(self.position_claimed.get(pos_key, u256(0)))
        if my_stake == 0 or already == 1:
            raise gl.vm.UserError("nothing_to_claim")

        if state == "INCONCLUSIVE":
            payout = my_stake
        else:
            winner = self.fixture_verdict[fixture_id]
            if my_outcome != winner:
                raise gl.vm.UserError("nothing_to_claim")
            total_pool = int(self.fixture_total_pool[fixture_id])
            fee_total, _resolver_share, _treasury_share = decisive_fee(total_pool)
            distributable = total_pool - fee_total
            winning_pool_total = int(self.pool_by_outcome[f"{fixture_id}:{winner}"])
            claimed_stake_before = int(self.fixture_claimed_stake[fixture_id])
            claimed_amount_before = int(self.fixture_claimed_amount[fixture_id])
            payout = compute_claim_payout(
                my_stake, winning_pool_total, distributable, claimed_stake_before, claimed_amount_before
            )
            self.fixture_claimed_stake[fixture_id] = u256(claimed_stake_before + my_stake)
            self.fixture_claimed_amount[fixture_id] = u256(claimed_amount_before + payout)

        self.position_claimed[pos_key] = u256(1)
        if payout > 0:
            _Recipient(gl.message.sender_address).emit_transfer(value=u256(payout))
        Claimed(fixture_id, gl.message.sender_address, u256(payout)).emit()
        return u256(payout)

    # ------------------------------------------------------------------
    # views
    # ------------------------------------------------------------------
    @gl.public.view
    def get_constitution(self, fixture_id: str) -> dict:
        self._require_exists(fixture_id)
        return constitution_view(
            fixture_id,
            self.fixture_home[fixture_id],
            self.fixture_away[fixture_id],
            int(self.fixture_kickoff[fixture_id]),
        )

    @gl.public.view
    def get_config(self) -> dict:
        d = get_constitution_dict()
        d["treasury"] = self.treasury.as_hex
        d["appeal_window_seconds"] = APPEAL_WINDOW
        d["total_fixtures"] = len(self.all_fixture_ids)
        d["chain_id"] = 61997
        d["network"] = "studio-dev"
        d["state_may_reset"] = True
        return d

    @gl.public.view
    def get_registry(self) -> dict:
        return {
            k: {"host": v["host"], "format": v["format"], "html_table": v["html_table"]}
            for k, v in PUBLISHER_REGISTRY.items()
        }

    @gl.public.view
    def get_fixture(self, fixture_id: str) -> dict:
        self._require_exists(fixture_id)
        return self._fixture_view(fixture_id)

    @gl.public.view
    def get_board(self, cursor: u256, limit: u256, state_filter: str) -> dict:
        ids = [self.all_fixture_ids[i] for i in range(len(self.all_fixture_ids))]
        if state_filter:
            ids = [fid for fid in ids if self.fixture_state[fid] == state_filter]
        start, end = 0, 0
        page_ids, next_cursor = paginate(ids, int(cursor), int(limit))
        return {"rows": [self._fixture_view(fid) for fid in page_ids], "next_cursor": next_cursor}

    @gl.public.view
    def get_scoreline(self, fixture_id: str) -> dict:
        self._require_exists(fixture_id)
        raw = self.fixture_scoreline_json.get(fixture_id, "")
        return json.loads(raw) if raw else {}

    @gl.public.view
    def get_record(self, fixture_id: str) -> dict:
        self._require_exists(fixture_id)
        return {
            "fixture_id": fixture_id,
            "state": self.fixture_state[fixture_id],
            "verdict": self.fixture_verdict.get(fixture_id, "") or None,
            "code": self.fixture_code.get(fixture_id, "") or None,
            "scoreline": self.get_scoreline(fixture_id) or None,
            "resolver": self.fixture_resolver.get(fixture_id, "") or None,
        }

    @gl.public.view
    def get_position(self, fixture_id: str, address: str) -> dict:
        self._require_exists(fixture_id)
        addr = Address(address).as_hex
        pos_key = f"{fixture_id}:{addr}"
        return {
            "fixture_id": fixture_id,
            "address": addr,
            "outcome": self.position_outcome.get(pos_key, "") or None,
            "amount": int(self.position_amount.get(pos_key, u256(0))),
            "claimed": bool(int(self.position_claimed.get(pos_key, u256(0)))),
        }

    @gl.public.view
    def get_positions(self, address: str, cursor: u256, limit: u256) -> dict:
        addr = Address(address).as_hex
        ids_container = self.user_fixture_ids.get(addr, None)
        ids = [ids_container[i] for i in range(len(ids_container))] if ids_container is not None else []
        page_ids, next_cursor = paginate(ids, int(cursor), int(limit))
        rows = []
        for fid in page_ids:
            pos_key = f"{fid}:{addr}"
            rows.append({
                "fixture_id": fid,
                "state": self.fixture_state[fid],
                "outcome": self.position_outcome.get(pos_key, "") or None,
                "amount": int(self.position_amount.get(pos_key, u256(0))),
                "claimed": bool(int(self.position_claimed.get(pos_key, u256(0)))),
            })
        return {"rows": rows, "next_cursor": next_cursor}

    @gl.public.view
    def get_claimable(self, address: str, cursor: u256, limit: u256) -> dict:
        addr = Address(address).as_hex
        ids_container = self.user_fixture_ids.get(addr, None)
        ids = [ids_container[i] for i in range(len(ids_container))] if ids_container is not None else []
        claimable = []
        for fid in ids:
            state = self.fixture_state[fid]
            if state not in ("FINALIZED", "INCONCLUSIVE"):
                continue
            pos_key = f"{fid}:{addr}"
            if bool(int(self.position_claimed.get(pos_key, u256(0)))):
                continue
            stake = int(self.position_amount.get(pos_key, u256(0)))
            if stake == 0:
                continue
            if state == "FINALIZED" and self.position_outcome.get(pos_key, "") != self.fixture_verdict[fid]:
                continue
            claimable.append(fid)
        page_ids, next_cursor = paginate(claimable, int(cursor), int(limit))
        return {"rows": [self._fixture_view(fid) for fid in page_ids], "next_cursor": next_cursor}

    @gl.public.view
    def get_activity(self, address: str, cursor: u256, limit: u256) -> dict:
        return self.get_positions(address, cursor, limit)
