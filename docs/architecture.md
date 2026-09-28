# Architecture

## State machine

```
OPEN --(kickoff passes, >=1 bet)--> [resolve()] --> PENDING --(appeal window elapses)--> [finalize()] --> FINALIZED | INCONCLUSIVE
OPEN --(creator, zero bets)--------> [cancel_fixture()]  --> CANCELED
OPEN --(kickoff passed, zero bets)-> [expire_fixture()]  --> EXPIRED
PENDING --(any bettor, in window)--> [appeal()] --> APPEALED --(re_adjudicate())--> PENDING (fresh window)
APPEALED --(1h stall)--------------> [lapse_appeal()] --> PENDING (prior verdict restored)
OPEN | PENDING | APPEALED --(7d after kickoff)--> [recover_refund()] --> INCONCLUSIVE
```

`LOCKED` (the spec's kickoff-passed-but-not-yet-resolved state) is not a
separate stored value -- `get_fixture()` derives it (`state == "OPEN" and
now >= kickoff`) since nothing in the write API needs to distinguish it
from `OPEN` server-side.

`APPEAL_WINDOW` (30 minutes) is a deliberate default this build chose --
the original brief fixed every other duration (`RESOLVE_EARLIEST_OFFSET`,
`RESOLVE_LATEST_OFFSET`, `LAPSE_APPEAL_STALL`, `RECOVER_REFUND_AFTER`) but
left the gap between `resolve()` and `finalize()` unspecified. 30 minutes
is long enough for a bettor to notice and react to a fresh verdict, short
enough that a decisive pot isn't held up for long. It's a named constant
(`Whistle.py`'s `APPEAL_WINDOW`), not a magic number, and easy to revisit.

## The comparator (`whistle_lib.py`, zero `genlayer` import)

No LLM is involved anywhere in this contract. Each desk's response is
fetched via a plain `gl.nondet.web.get(url)` and parsed into exactly one
thing per desk -- `{status, home, away, asof}` -- by deterministic
Python. The non-determinism GenVM's consensus is checking is purely "did
two validators' own independent live HTTP fetches produce the same
parsed facts", not any model sampling. The contract **never reads** a
1X2 claim from anywhere but its own `derive_1x2` function.

1. `parse_response_body(desk_id, raw_text)` -- bounds response size,
   decodes JSON, extracts the four fields in that desk's own shape.
2. `evaluate_sources(sources)` -- recomputes usability itself (`status ==
   "FT"` and both goal counts are valid non-negative ints); a desk
   claiming `usable: true` while `status != "FT"` is still treated as
   unusable. Requires **both** desks usable and reporting an **identical**
   scoreline; anything else returns a refund code (`MISSING`, `CONFLICT`,
   `LIVE`, `PRE`, `POSTPONED`, `ABANDONED`).
3. `derive_1x2(home, away)` -- three lines, pure, the only place a
   HOME/DRAW/AWAY verdict is ever produced.
4. `build_envelope(fixture_id, sources_raw)` -- assembles the full
   envelope (`fixture_id`, `sources`, `scoreline`, `verdict_1x2`, `code`)
   by calling the three functions above. Both `leader_fn` and
   `validator_fn` build one of these from their **own** independently
   fetched `sources_raw`.
5. `is_well_formed_envelope(envelope, fixture_id)` -- **recomputes**
   `code`/`scoreline`/`verdict_1x2` from the envelope's own claimed
   `sources` and requires an exact match. A leader that reports scoreline
   1-2 but a tampered `verdict_1x2` of `"HOME"` is rejected here alone,
   with no second fetch needed -- see `test_is_well_formed_rejects_lying_leader_verdict`.
6. `compare_envelopes(mine, leader, fixture_id)` -- the `validator_fn`
   equivalence check: both envelopes must be well-formed AND agree on
   `(code, verdict_1x2, scoreline)`. `asof` and any raw response shape
   are **never** compared, since two honest fetches of the same real
   match at two different real moments will legitimately differ there.

`gltest` direct-mode's `run_nondet` mock only ever invokes `leader_fn`,
never `validator_fn` -- so the equivalence check itself (item 6, and the
self-consistency check in item 5) is proven with hand-constructed
mismatched fixtures in `tests/direct/test_whistle_lib.py`, not via a live
two-validator `gltest` run.

`validator_fn` re-derives its own answer via `gl.vm.spawn_sandbox(leader_fn)`,
not a bare second call to `leader_fn()` -- `gl.eq_principle.strict_eq`'s
own validator does exactly this internally (confirmed by reading
`genlayer/eq_principle/__init__.py`), and a bare in-process re-call from
inside a validator has previously been observed live triggering a
GenVM-level `DETERMINISTIC_VIOLATION` vote even when the two results
genuinely matched. `strict_eq` itself wasn't used directly because its
bit-exact comparison would reject on `sources`' own volatile `asof`
field, which this design deliberately tolerates differing between two
independent fetches -- `compare_envelopes` needs to compare only the
derived `(code, verdict_1x2, scoreline)` facts, so the hand-rolled
`run_nondet` + `spawn_sandbox` combination is used instead, keeping
`strict_eq`'s safer re-invocation mechanism without its stricter
equality rule.

## Two deliberate, toolchain-forced deviations from the original brief

1. **`raise gl.vm.UserError(...)`, not `gl.vm.UserError.immediate(...)`.**
   The brief asked for `.immediate(...)`. `gltest`'s direct-mode mock
   implements it as a bare `assert False` (confirmed by reading
   `genlayer/_internal/on_chain/gl_call.py` in the pinned SDK), which
   discards the error string entirely -- no local test can assert on
   *which* guard fired, only that *something* raised. `raise
   UserError(...)` is the same real, live GenVM user-error path with the
   message intact end to end, and is what every prior GenLayer project on
   this account's toolchain has proven testable.
2. **`gl.vm.run_nondet`, not `gl.vm.run_nondet_default`.** The brief
   named `run_nondet_default` for the money path -- a real function in
   the pinned SDK (confirmed by reading `genlayer/vm/__init__.py`
   directly), and genuinely the "recommended" API per its own docstring.
   The latest available `genvm-linter` (`0.11.1rc2` -- confirmed no
   newer release exists via `pip index versions genvm-linter --pre`)
   only statically recognizes `run_nondet`/`run_nondet_unsafe` as
   equivalence-principle-establishing calls; `run_nondet_default` trips
   E010 ("gl.nondet.* call ... not reachable from equivalence principle
   block") as a false positive. Since lint-cleanliness is a real,
   previously-confirmed portal-rejection factor on this account (see
   `docs/audit.md`), `run_nondet` -- functionally the same primitive,
   just without `run_nondet_default`'s automatic sandboxed
   error-comparison, which this contract's `leader_fn` never needs since
   it never raises -- is used instead.

## `genlayer deploy --args` gotcha (confirmed live, 2026-09-26)

The installed `genlayer` CLI's `--args` parser (`parseArg`/`parseScalar` in
the installed package) only uses its own `JSON.parse` result for
object/array values -- for a plain scalar it always falls through to
`parseScalar` on the **original, unparsed** argument text. JSON-quoting a
single string arg (`--args '"0xADDR"'`) therefore does **not** strip the
quote characters -- they get sent as literal characters embedded in the
string, which broke `Address(treasury)` in the constructor
(`FINISHED_WITH_ERROR`, confirmed by decoding the actual submitted
calldata off the explorer API). A **bare, unquoted** address argument
(`--args 0xADDR`) works instead: the parser auto-detects it as its
"address" calldata type, and GenVM correctly binds that to a Python
`treasury: str` parameter. See `docs/STATUS.md`'s deploy log for the full
before/after.

## Toolchain version table

| Tool | Version | Notes |
|---|---|---|
| `genlayer` CLI | `0.40.0-rc.3` | only release that supports Studio Next |
| `genlayer-test` (`gltest`) | `0.30.0rc2` | direct-mode pytest plugin |
| `genvm-linter` | `0.11.1rc2` | latest available, confirmed via `pip index versions --pre` |
| `genlayer-js` | `2.0.0-rc.1` | frontend + deploy script |
| pinned `Depends` hash | `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` | resolves to SDK generation `v0.6.0-rc6` |

## Publisher registry (`whistle_lib.PUBLISHER_REGISTRY`)

Two locked desks, JSON only (`html_table: false` for both in this V1),
fixed host + path per desk -- `build_desk_url` never accepts a
caller-supplied URL, only that desk's own publisher-side reference.

**The desks do not share an id space, and a fixture names each one
separately.** `desk_a` is keyed by TheSportsDB's `idEvent`, `desk_b` by
OpenLigaDB's `matchID`; the same integer denotes unrelated matches on the
two services. Both references are supplied once at `create_fixture`,
validated as bare digit strings (`is_valid_desk_ref`, max
`MAX_DESK_REF_LEN`) so neither can smuggle a path, query or second host
into an otherwise locked URL, and frozen for the fixture's life.
`get_fixture` and `get_constitution` both expose them, so anyone can
re-fetch both desks by hand and audit a verdict independently.

**Competition.** OpenLigaDB carries German league football only, so the
Bundesliga (`COMPETITION = "BL1"`) is the overlap with TheSportsDB. A
competition only one desk covers could never reach two matching FT
scorelines, and would settle every fixture INCONCLUSIVE.

**Response shapes are taken from live fetches, not documentation.** Both
were captured from the real endpoints and are pinned by tests:

| | `desk_a` (TheSportsDB) | `desk_b` (OpenLigaDB) |
|---|---|---|
| Completion | `strStatus` is **null** on the free tier even for long-finished matches, so FT is inferred from a full integer scoreline with `strPostponed == "no"`; an explicit status is honoured when present | boolean `matchIsFinished` |
| Goals | `intHomeScore` / `intAwayScore` (strings) | `matchResults[]`, the entry whose `resultTypeKind` is `After90Minutes` -> `pointsTeam1` / `pointsTeam2` |
| `asof` | `strTimestamp` | `lastUpdateDateTime` |

Inferring desk_a's completion from a scoreline is safe because it is
never the only evidence: `resolve()` can only run 105+ minutes after
kickoff, and desk_b must **independently** report the match finished for
the fixture to settle decisively. `desk_b`'s `After90Minutes` selection
is what makes `RESULT_TYPE = "FT_90"` literally true -- the extra-time
and penalties entries are explicitly excluded, so a shootout can never
be read as the full-time scoreline.

A reference that does not exist on OpenLigaDB answers with **plain text**
(`No match with Id ... found!`), not JSON, which `parse_response_body`
reports as `decode_fail` -- unusable, never decisive.

## Payout math (`whistle_lib.compute_claim_payout`)

Pari-mutuel, pro-rata, floor-divided: `payout = my_stake *
distributable // winning_pool_total`. The claim that exhausts the
winning pool's total staked amount instead receives the exact remainder
(`distributable - claimed_amount_before`), so floor-division dust never
gets permanently stranded in the contract -- see
`test_claim_payout_last_claimant_gets_dust`.

## Bonds vs. fees

Bonds (`CREATE_BOND`, `RESOLVE_BOND`) are refundable deposits, returned
via `reclaim_bonds()` -- a separate pull, not auto-paid at `finalize()`
time, mirroring how every other GenLayer market on this account handles
bond escrow. The decisive fee (2% of the pot, split 50/50
resolver/treasury) is **not** a bond; it is paid out immediately inside
`finalize()`, since it is earned income rather than a returnable deposit.
