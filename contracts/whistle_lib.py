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
from __future__ import annotations

# ---------------------------------------------------------------------------
# Constitution / constants (frozen; mirrored by Whistle.get_constitution())
# ---------------------------------------------------------------------------

COMPETITION = "UCL_LP"                 # V1 template: UEFA league-phase, 90 min only
RESULT_TYPE = "FT_90"
MARKET = "1X2"
OUTCOMES: tuple[str, str, str] = ("HOME", "DRAW", "AWAY")
DESK_IDS: tuple[str, str] = ("desk_a", "desk_b")

MIN_LEAD = 7200                        # fixture must be created >= 2h before kickoff
MIN_BET = 10**18                       # 1 GEN
CREATE_BOND = 5 * 10**16               # 0.05 GEN
RESOLVE_BOND = 2 * 10**16              # 0.02 GEN
FEE_BPS = 200                          # 2% of the decisive pot
APPEAL_BOND_FLOOR = 5 * 10**16         # 0.05 GEN
LAPSE_APPEAL_STALL = 3600              # 1h
RECOVER_REFUND_AFTER = 7 * 24 * 3600   # 7 days
MAX_OPEN_PER_CREATOR = 16
MAX_PAGE_SIZE = 50

RESOLVE_EARLIEST_OFFSET = 6300         # kickoff + 105 min (90' + stoppage buffer)
RESOLVE_LATEST_OFFSET = 36 * 3600      # kickoff + 36h -> INCONCLUSIVE fallback

VALID_APPEAL_GROUNDS: tuple[str, str, str, str] = ("SCORE", "STATUS", "FIXTURE", "REVISED")
VALID_STATUSES: tuple[str, str, str, str, str, str] = (
    "FT", "LIVE", "PRE", "POSTPONED", "ABANDONED", "UNKNOWN",
)

U256_MAX = 2**256 - 1

# Locked publisher endpoints -- never accept a caller-supplied URL. Each
# desk is queried by the SAME fixture_id; both desks are assumed to share
# a canonical id space for this V1 template. Response format is JSON for
# both desks in V1 (html_table unused).
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


# ---------------------------------------------------------------------------
# Overflow guard
# ---------------------------------------------------------------------------

def assert_u256(x: int) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"not an int: {x!r}")
    if x < 0 or x > U256_MAX:
        raise ValueError(f"value out of u256 range: {x}")
    return x


# ---------------------------------------------------------------------------
# Locked URL builders -- fixed host/path per desk, fixture_id is the only
# variable. Callers never supply a URL.
# ---------------------------------------------------------------------------

def build_desk_url(desk_id: str, fixture_id: str) -> str:
    if desk_id not in PUBLISHER_REGISTRY:
        raise ValueError(f"unknown desk: {desk_id}")
    reg = PUBLISHER_REGISTRY[desk_id]
    if desk_id == "desk_a":
        return f"{reg['host']}{reg['path']}?id={fixture_id}"
    return f"{reg['host']}{reg['path']}/{fixture_id}"


# ---------------------------------------------------------------------------
# Constitution validation (frozen at create_fixture)
# ---------------------------------------------------------------------------

class WhistleValidationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_constitution(payload: dict, now_ts: int, open_count_for_creator: int) -> None:
    if not isinstance(payload, dict):
        raise WhistleValidationError("malformed_constitution")
    for key in ("fixture_id", "home", "away", "kickoff_unix"):
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
    if open_count_for_creator >= MAX_OPEN_PER_CREATOR:
        raise WhistleValidationError("creator_cap_reached")


def constitution_view(fixture_id: str, home: str, away: str, kickoff_unix: int) -> dict:
    return {
        "competition": COMPETITION,
        "fixture_id": fixture_id,
        "home": home,
        "away": away,
        "kickoff_unix": kickoff_unix,
        "publishers": list(DESK_IDS),
        "result_type": RESULT_TYPE,
        "market": MARKET,
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
    }


# ---------------------------------------------------------------------------
# Per-desk source parsing -> the ONLY thing a model is ever asked to
# extract is these raw structured facts. It never derives a 1X2 verdict.
# ---------------------------------------------------------------------------

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
        status_raw = str(row.get("strStatus") or "").upper()
        home_raw, away_raw = row.get("intHomeScore"), row.get("intAwayScore")
        asof = row.get("strTimestamp") or 0
    elif desk_id == "desk_b":
        if not isinstance(body, dict):
            return {"usable": False, "reason": "malformed_event"}
        status_raw = str(body.get("matchStatus") or "").upper()
        home_raw, away_raw = body.get("homeGoals"), body.get("awayGoals")
        asof = body.get("lastUpdate") or 0
    else:
        return {"usable": False, "reason": "unknown_desk"}

    status = _normalize_status(status_raw)
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


# ---------------------------------------------------------------------------
# Code-side derivation. Model NEVER returns HOME/DRAW/AWAY -- it (via
# parse_response_body above) only ever produces raw per-desk facts; this
# function derives everything downstream deterministically.
# ---------------------------------------------------------------------------

def derive_1x2(home: int, away: int) -> str:
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def _source_ok(src: object) -> tuple[bool, int | None, int | None]:
    """Recomputes usability from status/goals directly -- never trusts a
    model-claimed `usable` flag blindly."""
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

    (ha, aa), (hb, ab) = reports  # type: ignore[misc]
    if ha != hb or aa != ab:
        return "CONFLICT", None
    return "CLEAR", {"home": ha, "away": aa, "status": "FT"}


def build_envelope(fixture_id: str, sources_raw: dict) -> dict:
    """Pure: given the model's raw structured per-desk extraction
    (sources_raw), deterministically derive scoreline/verdict_1x2/code.
    This is what BOTH leader_fn and validator_fn build from their own
    independently-fetched sources_raw -- code always recomputes verdict
    from scoreline; a model can never make the contract believe a
    HOME/DRAW/AWAY it didn't derive from matching FT goals itself."""
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


# ---------------------------------------------------------------------------
# Fee / bond / payout math
# ---------------------------------------------------------------------------

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
