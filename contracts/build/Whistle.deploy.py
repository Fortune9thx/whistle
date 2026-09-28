# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""
WHISTLE pure-Python logic: constants, publisher adapters, bps/fee math,
the two-publisher FT-scoreline comparator, and pari-mutuel payout math.

Deliberately has ZERO import of `genlayer`/`gl` so it can be unit-tested
directly with plain pytest, with no GenVM sandbox, no gltest direct-mode
deploy, and no dependency on the local toolchain's runner-hash resolution
working. Whistle.py imports this module and wires it into gl.public
methods and gl.vm.run_nondet_default leader/validator closures.

This split exists because gltest direct-mode cannot exercise a
run_nondet_default validator_fn at all (it only ever invokes leader_fn) --
the independently-reproducible logic validator_fn is built from (envelope
construction, the scoreline comparator, the 1X2 derivation, fee/payout
math) has to be provable some other way. See docs/architecture.md.
"""





COMPETITION = "BL1"

RESULT_TYPE = "FT_90"

MARKET = "1X2"

OUTCOMES: tuple[str, str, str] = ("HOME", "DRAW", "AWAY")

DESK_IDS: tuple[str, str] = ("desk_a", "desk_b")



MIN_LEAD = 7200

MIN_BET = 10**18

CREATE_BOND = 5 * 10**16

RESOLVE_BOND = 2 * 10**16

FEE_BPS = 200

APPEAL_BOND_FLOOR = 5 * 10**16

LAPSE_APPEAL_STALL = 3600

RECOVER_REFUND_AFTER = 7 * 24 * 3600

MAX_OPEN_PER_CREATOR = 16

MAX_PAGE_SIZE = 50



RESOLVE_EARLIEST_OFFSET = 6300

RESOLVE_LATEST_OFFSET = 36 * 3600



VALID_APPEAL_GROUNDS: tuple[str, str, str, str] = ("SCORE", "STATUS", "FIXTURE", "REVISED")

VALID_STATUSES: tuple[str, str, str, str, str, str] = (

    "FT", "LIVE", "PRE", "POSTPONED", "ABANDONED", "UNKNOWN",

)



U256_MAX = 2**256 - 1



PUBLISHER_REGISTRY: dict[str, dict] = {

    "desk_a": {

        "host": "https://www.thesportsdb.com",

        "path": "/api/v1/json/3/lookupevent.php",

        "format": "json",

        "html_table": False,

    },

    "desk_b": {

        "host": "https://api.openligadb.de",

        "path": "/getmatchdata",

        "format": "json",

        "html_table": False,

    },

}



MAX_RESPONSE_BYTES = 65_536







def assert_u256(x: int) -> int:

    if not isinstance(x, int) or isinstance(x, bool):

        raise ValueError(f"not an int: {x!r}")

    if x < 0 or x > U256_MAX:

        raise ValueError(f"value out of u256 range: {x}")

    return x







def build_desk_url(desk_id: str, desk_ref: str) -> str:

    """`desk_ref` is that desk's OWN publisher-side identifier, frozen at
    create_fixture -- TheSportsDB's idEvent for desk_a, OpenLigaDB's
    matchID for desk_b. Validated to be a bare digit string before it is
    ever stored, so it cannot smuggle a path or query into the URL."""

    if desk_id not in PUBLISHER_REGISTRY:

        raise ValueError(f"unknown desk: {desk_id}")

    if not is_valid_desk_ref(desk_ref):

        raise ValueError(f"bad desk ref: {desk_ref!r}")

    reg = PUBLISHER_REGISTRY[desk_id]

    if desk_id == "desk_a":

        return f"{reg['host']}{reg['path']}?id={desk_ref}"

    return f"{reg['host']}{reg['path']}/{desk_ref}"





MAX_DESK_REF_LEN = 24





def is_valid_desk_ref(desk_ref: object) -> bool:

    """A publisher reference is a bare run of digits. Rejecting anything
    else keeps a caller from injecting `../`, a query string or a second
    host into an otherwise locked URL."""

    if not isinstance(desk_ref, str):

        return False

    s = desk_ref.strip()

    return 0 < len(s) <= MAX_DESK_REF_LEN and s.isdigit()







class WhistleValidationError(Exception):

    def __init__(self, code: str):

        super().__init__(code)

        self.code = code





def validate_constitution(payload: dict, now_ts: int, open_count_for_creator: int) -> None:

    if not isinstance(payload, dict):

        raise WhistleValidationError("malformed_constitution")

    for key in ("fixture_id", "home", "away", "kickoff_unix", "desk_a_ref", "desk_b_ref"):

        if key not in payload:

            raise WhistleValidationError(f"missing_{key}")

    fixture_id = payload["fixture_id"]

    if not isinstance(fixture_id, str) or not fixture_id.strip():

        raise WhistleValidationError("bad_fixture_id")

    home, away = payload["home"], payload["away"]

    if not isinstance(home, str) or not home.strip():

        raise WhistleValidationError("bad_home")

    if not isinstance(away, str) or not away.strip():

        raise WhistleValidationError("bad_away")

    if home.strip() == away.strip():

        raise WhistleValidationError("home_equals_away")

    kickoff = payload["kickoff_unix"]

    if not isinstance(kickoff, int) or isinstance(kickoff, bool):

        raise WhistleValidationError("bad_kickoff")

    if kickoff < now_ts + MIN_LEAD:

        raise WhistleValidationError("below_min_lead")

    if not is_valid_desk_ref(payload["desk_a_ref"]):

        raise WhistleValidationError("bad_desk_a_ref")

    if not is_valid_desk_ref(payload["desk_b_ref"]):

        raise WhistleValidationError("bad_desk_b_ref")

    if open_count_for_creator >= MAX_OPEN_PER_CREATOR:

        raise WhistleValidationError("creator_cap_reached")





def constitution_view(

    fixture_id: str,

    home: str,

    away: str,

    kickoff_unix: int,

    desk_a_ref: str = "",

    desk_b_ref: str = "",

) -> dict:

    return {

        "competition": COMPETITION,

        "fixture_id": fixture_id,

        "home": home,

        "away": away,

        "kickoff_unix": kickoff_unix,

        "publishers": list(DESK_IDS),

        "result_type": RESULT_TYPE,

        "market": MARKET,

        "desk_refs": {"desk_a": desk_a_ref, "desk_b": desk_b_ref},

        "source_urls": {

            "desk_a": build_desk_url("desk_a", desk_a_ref) if is_valid_desk_ref(desk_a_ref) else "",

            "desk_b": build_desk_url("desk_b", desk_b_ref) if is_valid_desk_ref(desk_b_ref) else "",

        },

    }





def get_constitution_dict() -> dict:

    return {

        "competition": COMPETITION,

        "result_type": RESULT_TYPE,

        "market": MARKET,

        "publishers": list(DESK_IDS),

        "min_lead_seconds": MIN_LEAD,

        "min_bet_wei": MIN_BET,

        "create_bond_wei": CREATE_BOND,

        "resolve_bond_wei": RESOLVE_BOND,

        "fee_bps": FEE_BPS,

        "appeal_bond_floor_wei": APPEAL_BOND_FLOOR,

        "resolve_earliest_offset": RESOLVE_EARLIEST_OFFSET,

        "resolve_latest_offset": RESOLVE_LATEST_OFFSET,

        "lapse_appeal_stall": LAPSE_APPEAL_STALL,

        "recover_refund_after": RECOVER_REFUND_AFTER,

        "max_open_per_creator": MAX_OPEN_PER_CREATOR,

        "max_page_size": MAX_PAGE_SIZE,

        "valid_appeal_grounds": list(VALID_APPEAL_GROUNDS),

        "max_desk_ref_len": MAX_DESK_REF_LEN,

    }







def parse_response_body(desk_id: str, raw_text: str | None) -> dict:

    """Bound response size, decode JSON, extract {status, home, away, asof}
    in a desk-specific shape. Returns {"usable": False, "reason": ...} on
    any parse/shape failure -- never raises."""

    import json



    if raw_text is None:

        return {"usable": False, "reason": "missing_body"}

    if len(raw_text.encode("utf-8", errors="ignore")) > MAX_RESPONSE_BYTES:

        return {"usable": False, "reason": "response_too_large"}

    try:

        body = json.loads(raw_text)

    except (ValueError, TypeError):

        return {"usable": False, "reason": "decode_fail"}



    if desk_id == "desk_a":

        events = body.get("events") if isinstance(body, dict) else None

        if not isinstance(events, list) or len(events) == 0:

            return {"usable": False, "reason": "missing_event"}

        row = events[0]

        if not isinstance(row, dict):

            return {"usable": False, "reason": "malformed_event"}

        home_raw, away_raw = row.get("intHomeScore"), row.get("intAwayScore")

        asof = row.get("strTimestamp") or 0

        status = _desk_a_status(row, home_raw, away_raw)

    elif desk_id == "desk_b":

        if not isinstance(body, dict):

            return {"usable": False, "reason": "malformed_event"}

        asof = body.get("lastUpdateDateTime") or 0

        home_raw, away_raw = _desk_b_goals(body.get("matchResults"))

        status = "FT" if body.get("matchIsFinished") is True else "LIVE"

    else:

        return {"usable": False, "reason": "unknown_desk"}



    home = _to_nonneg_int(home_raw)

    away = _to_nonneg_int(away_raw)

    usable = status == "FT" and home is not None and away is not None

    return {

        "usable": usable,

        "status": status,

        "home": home,

        "away": away,

        "asof": asof,

    }





def _desk_a_status(row: dict, home_raw: object, away_raw: object) -> str:

    """TheSportsDB free tier leaves strStatus null on finished matches, so
    an explicit status is honoured when present and completion is
    otherwise inferred from a full integer scoreline on a match that was
    not postponed."""

    explicit = str(row.get("strStatus") or row.get("strStatusShort") or "").strip()

    if explicit:

        normalized = _normalize_status(explicit)

        if normalized != "UNKNOWN":

            return normalized

    if str(row.get("strPostponed") or "").strip().lower() in ("yes", "true", "1"):

        return "POSTPONED"

    if _to_nonneg_int(home_raw) is None or _to_nonneg_int(away_raw) is None:

        return "PRE"

    return "FT"





def _desk_b_goals(results: object) -> tuple[object, object]:

    """Pull the 90-minute result out of OpenLigaDB's matchResults list.
    Prefers the explicit After90Minutes entry; falls back to the lowest
    resultOrderID that is not extra time or penalties, so a shootout
    scoreline can never be read as the full-time one."""

    if not isinstance(results, list):

        return None, None

    ninety = None

    for entry in results:

        if not isinstance(entry, dict):

            continue

        kind = str(entry.get("resultTypeKind") or "").strip()

        if kind == "After90Minutes":

            ninety = entry

            break

    if ninety is None:

        candidates = [

            e for e in results

            if isinstance(e, dict)

            and str(e.get("resultTypeKind") or "").strip() not in ("AfterExtraTime", "AfterPenalties")

            and str(e.get("resultTypeKind") or "").strip() != "HalfTime"

        ]

        if len(candidates) != 1:

            return None, None

        ninety = candidates[0]

    return ninety.get("pointsTeam1"), ninety.get("pointsTeam2")





def _normalize_status(raw: str) -> str:

    raw = (raw or "").strip().upper()

    if raw in ("FT", "MATCH FINISHED", "FINISHED", "FULL TIME"):

        return "FT"

    if raw in ("LIVE", "IN PLAY", "1H", "2H", "HT"):

        return "LIVE"

    if raw in ("NS", "PRE", "SCHEDULED", "NOT STARTED"):

        return "PRE"

    if raw in ("POSTPONED", "PPD"):

        return "POSTPONED"

    if raw in ("ABANDONED", "ABD", "CANCELLED", "CANCELED"):

        return "ABANDONED"

    return "UNKNOWN"





def _to_nonneg_int(raw) -> int | None:

    if raw is None:

        return None

    if isinstance(raw, bool):

        return None

    if isinstance(raw, int):

        return raw if raw >= 0 else None

    try:

        s = str(raw).strip()

        if not s.isdigit():

            return None

        return int(s)

    except (TypeError, ValueError):

        return None







def derive_1x2(home: int, away: int) -> str:

    if home > away:

        return "HOME"

    if home < away:

        return "AWAY"

    return "DRAW"





def _source_ok(src: object) -> tuple[bool, int | None, int | None]:

    """Recomputes usability from status/goals directly -- never trusts the
    `usable` flag a parsed source carries."""

    if not isinstance(src, dict):

        return False, None, None

    status = src.get("status")

    if status not in VALID_STATUSES or status != "FT":

        return False, None, None

    home, away = src.get("home"), src.get("away")

    if not isinstance(home, int) or isinstance(home, bool) or home < 0:

        return False, None, None

    if not isinstance(away, int) or isinstance(away, bool) or away < 0:

        return False, None, None

    return True, home, away





def evaluate_sources(sources: dict) -> tuple[str, dict | None]:

    """Returns (code, scoreline_or_None). Requires BOTH locked desks
    usable and reporting an identical FT scoreline -- anything else is a
    refund-coded (INCONCLUSIVE) outcome, never a decisive one."""

    if not isinstance(sources, dict):

        return "MISSING", None



    reports: list[tuple[int, int] | None] = []

    statuses: list[str | None] = []

    for desk in DESK_IDS:

        src = sources.get(desk)

        statuses.append(src.get("status") if isinstance(src, dict) else None)

        ok, home, away = _source_ok(src)

        reports.append((home, away) if ok and home is not None and away is not None else None)



    if any(r is None for r in reports):

        if "POSTPONED" in statuses:

            return "POSTPONED", None

        if "ABANDONED" in statuses:

            return "ABANDONED", None

        if "LIVE" in statuses:

            return "LIVE", None

        if "PRE" in statuses:

            return "PRE", None

        return "MISSING", None



    first, second = reports

    if first is None or second is None:

        return "MISSING", None

    (ha, aa), (hb, ab) = first, second

    if ha != hb or aa != ab:

        return "CONFLICT", None

    return "CLEAR", {"home": ha, "away": aa, "status": "FT"}





def build_envelope(fixture_id: str, sources_raw: dict) -> dict:

    """Pure: given the raw structured per-desk extraction (sources_raw,
    already parsed by deterministic code -- no LLM involved anywhere),
    derive scoreline/verdict_1x2/code.
    This is what BOTH leader_fn and validator_fn build from their own
    independently-fetched sources_raw -- code always recomputes verdict
    from scoreline, so no leader can make the contract believe a
    HOME/DRAW/AWAY it did not derive from matching FT goals itself."""

    code, scoreline = evaluate_sources(sources_raw)

    verdict = derive_1x2(scoreline["home"], scoreline["away"]) if scoreline else "INCONCLUSIVE"

    return {

        "fixture_id": fixture_id,

        "sources": sources_raw,

        "scoreline": scoreline,

        "verdict_1x2": verdict,

        "code": code,

    }





def is_well_formed_envelope(envelope, fixture_id: str) -> bool:

    """Structural + self-consistency check. Recomputes code/verdict from
    the envelope's OWN claimed sources/scoreline and REQUIRES the claimed
    verdict_1x2/code match that recomputation exactly -- a leader (honest
    or compromised) that reports a verdict_1x2 inconsistent with its own
    scoreline is rejected here, with zero dependence on a second fetch."""

    if not isinstance(envelope, dict):

        return False

    required = {"fixture_id", "sources", "scoreline", "verdict_1x2", "code"}

    if not required.issubset(envelope.keys()):

        return False

    if envelope["fixture_id"] != fixture_id:

        return False

    if envelope["verdict_1x2"] not in OUTCOMES + ("INCONCLUSIVE",):

        return False



    expected_code, expected_scoreline = evaluate_sources(envelope["sources"])

    if expected_code != envelope["code"]:

        return False

    if expected_scoreline != envelope["scoreline"]:

        return False

    expected_verdict = (

        derive_1x2(expected_scoreline["home"], expected_scoreline["away"])

        if expected_scoreline

        else "INCONCLUSIVE"

    )

    if expected_verdict != envelope["verdict_1x2"]:

        return False

    return True





def compare_envelopes(mine: dict, leader: dict, fixture_id: str) -> bool:

    """The equivalence comparator a validator_fn runs: reject malformed
    output on either side, then ACCEPT iff the two independently-derived
    (code, verdict_1x2, scoreline) triples match exactly. `asof` and any
    raw HTML/prose the two fetches saw are NEVER compared -- only the
    derived facts, since asof legitimately differs between two fetches of
    the same real match at two different real moments."""

    if not is_well_formed_envelope(leader, fixture_id):

        return False

    if not is_well_formed_envelope(mine, fixture_id):

        return False

    return (

        mine["code"] == leader["code"]

        and mine["verdict_1x2"] == leader["verdict_1x2"]

        and mine["scoreline"] == leader["scoreline"]

    )







def decisive_fee(pot: int) -> tuple[int, int, int]:

    """Returns (fee_total, resolver_share, treasury_share). 0% fee on
    refunds is enforced by the CALLER never invoking this for an
    INCONCLUSIVE outcome -- this function only ever runs on CLEAR."""

    fee_total = (pot * FEE_BPS) // 10_000

    resolver_share = fee_total // 2

    treasury_share = fee_total - resolver_share

    return fee_total, resolver_share, treasury_share





def appeal_bond_amount(winning_pool_total: int) -> int:

    return max(APPEAL_BOND_FLOOR, winning_pool_total // 2)





def compute_claim_payout(

    my_stake: int,

    winning_pool_total: int,

    distributable: int,

    claimed_stake_before: int,

    claimed_amount_before: int,

) -> int:

    """Pro-rata payout, floor-divided; the claim that exhausts the
    winning pool's total staked amount instead receives the exact
    remainder so floor-division dust never gets permanently stranded."""

    if winning_pool_total <= 0:

        raise ValueError("zero winning pool")

    is_last = (claimed_stake_before + my_stake) >= winning_pool_total

    if is_last:

        return distributable - claimed_amount_before

    return (my_stake * distributable) // winning_pool_total





def paginate(ids: list, cursor: int, limit: int) -> tuple[list, int]:

    lim = limit if 0 < limit <= MAX_PAGE_SIZE else MAX_PAGE_SIZE

    start = cursor if cursor > 0 else 0

    end = start + lim

    page = ids[start:end]

    next_cursor = end if end < len(ids) else 0

    return page, next_cursor



import json

from datetime import datetime, timezone



import genlayer as gl

from genlayer.storage import DynArray, TreeMap

from genlayer.types import Address, u256





APPEAL_WINDOW = 1800





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

    fixture_desk_a_ref: TreeMap[str, str]

    fixture_desk_b_ref: TreeMap[str, str]

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





    def _now_unix(self) -> int:

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

            "competition": COMPETITION,

            "home": self.fixture_home[fixture_id],

            "away": self.fixture_away[fixture_id],

            "kickoff_unix": kickoff,

            "desk_refs": {

                "desk_a": self.fixture_desk_a_ref.get(fixture_id, ""),

                "desk_b": self.fixture_desk_b_ref.get(fixture_id, ""),

            },

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



    @gl.public.write.payable

    def create_fixture(

        self,

        fixture_id: str,

        home: str,

        away: str,

        kickoff_unix: u256,

        desk_a_ref: str,

        desk_b_ref: str,

    ) -> str:

        """Creates a new fixture. Attached GEN must equal CREATE_BOND
        exactly -- no stake is required from the creator.

        `fixture_id` is this contract's own unique key. The two desks do
        NOT share an identifier space, so the publisher-side row on each
        is named separately: `desk_a_ref` is TheSportsDB's idEvent and
        `desk_b_ref` is OpenLigaDB's matchID for the same match. Both are
        frozen here and are the only caller-supplied part of either
        locked URL -- each must be a bare digit string."""

        if fixture_id in self.fixture_state:

            raise gl.vm.UserError("duplicate_fixture")



        creator = self._sender()

        now_ts = self._now_unix()

        open_count = int(self.creator_open_count.get(creator, u256(0)))

        payload = {

            "fixture_id": fixture_id,

            "home": home,

            "away": away,

            "kickoff_unix": int(kickoff_unix),

            "desk_a_ref": desk_a_ref,

            "desk_b_ref": desk_b_ref,

        }

        try:

            validate_constitution(payload, now_ts=now_ts, open_count_for_creator=open_count)

        except WhistleValidationError as exc:

            raise gl.vm.UserError(exc.code)



        if int(gl.message.value) != CREATE_BOND:

            raise gl.vm.UserError("wrong_bond_amount")



        self.fixture_home[fixture_id] = home

        self.fixture_away[fixture_id] = away

        self.fixture_kickoff[fixture_id] = kickoff_unix

        self.fixture_desk_a_ref[fixture_id] = desk_a_ref.strip()

        self.fixture_desk_b_ref[fixture_id] = desk_b_ref.strip()

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



    def _resolve_core(self, fixture_id: str, resolver: str) -> str:

        kickoff = int(self.fixture_kickoff[fixture_id])

        now_ts = self._now_unix()



        if now_ts >= kickoff + RESOLVE_LATEST_OFFSET:

            verdict, code, scoreline = "INCONCLUSIVE", "WINDOW_EXPIRED", None

        else:

            fixture_id_local = fixture_id

            desk_refs_local = {

                "desk_a": str(self.fixture_desk_a_ref[fixture_id]),

                "desk_b": str(self.fixture_desk_b_ref[fixture_id]),

            }



            def leader_fn() -> str:

                sources_raw = {}

                for desk in DESK_IDS:

                    url = build_desk_url(desk, desk_refs_local[desk])

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

                my_result = gl.vm.spawn_sandbox(leader_fn)

                if not isinstance(my_result, gl.vm.Return):

                    return False

                try:

                    my_env = json.loads(str(my_result.calldata))

                except (ValueError, TypeError):

                    return False

                return compare_envelopes(my_env, leader_env, fixture_id_local)



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

        winning_pool_total = (

            int(self.pool_by_outcome.get(f"{fixture_id}:{verdict}", u256(0))) if verdict in OUTCOMES else 0

        )



        if verdict in OUTCOMES and winning_pool_total > 0:

            fee_total, resolver_share, treasury_share = decisive_fee(total_pool)

            resolver = self.fixture_resolver.get(fixture_id, "")

            if resolver_share > 0 and resolver:

                _Recipient(Address(resolver)).emit_transfer(value=u256(resolver_share))

            if treasury_share > 0:

                _Recipient(self.treasury).emit_transfer(value=u256(treasury_share))

            self.fixture_state[fixture_id] = "FINALIZED"

        else:

            if verdict in OUTCOMES:

                self.fixture_code[fixture_id] = "NO_STAKERS_ON_WINNER"

                self.fixture_verdict[fixture_id] = "INCONCLUSIVE"

            self.fixture_state[fixture_id] = "INCONCLUSIVE"



        self.fixture_last_state_change[fixture_id] = u256(now_ts)

        creator = self.fixture_creator[fixture_id]

        cur = int(self.creator_open_count.get(creator, u256(0)))

        if cur > 0:

            self.creator_open_count[creator] = u256(cur - 1)

        EventFinalized(fixture_id, self.fixture_verdict[fixture_id] or "INCONCLUSIVE").emit()



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



    @gl.public.view

    def get_constitution(self, fixture_id: str) -> dict:

        self._require_exists(fixture_id)

        return constitution_view(

            fixture_id,

            self.fixture_home[fixture_id],

            self.fixture_away[fixture_id],

            int(self.fixture_kickoff[fixture_id]),

            self.fixture_desk_a_ref.get(fixture_id, ""),

            self.fixture_desk_b_ref.get(fixture_id, ""),

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
