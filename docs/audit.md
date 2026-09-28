# Threat model / audit notes

## Adversary model

An attacker who controls, or can bribe, the leader validator for a
`resolve()`/`re_adjudicate()` call, and any ordinary wallet acting in its
own economic self-interest (betting after they already know the result,
appealing frivolously, racing to claim, etc.).

## Checked and confirmed safe

1. **Leader cannot fabricate a verdict.** `is_well_formed_envelope`
   recomputes `code`/`scoreline`/`verdict_1x2` from the envelope's own
   claimed `sources` and rejects any mismatch -- a leader would have to
   forge internally-consistent, matching `sources` for *both* desks, not
   just claim a verdict. See `test_is_well_formed_rejects_lying_leader_verdict`.
2. **A single desk's outage can't move the pot.** `evaluate_sources`
   requires both desks usable and matching; one desk down/timing out/
   still `LIVE` after the earliest-resolve offset yields a refund code,
   never a decisive one.
3. **No value leaves the contract except through `claim()`,
   `reclaim_bonds()`, or a direct fee transfer inside `finalize()`.**
   Every other write only mutates `TreeMap` state.
4. **Every bond-collecting write has a matching bond-disposing path** on
   both its normal and its escape-hatch route: `create_fixture` (bond
   collected) pairs with `cancel_fixture`/`expire_fixture`/
   `reclaim_bonds`; `resolve`/`re_adjudicate` (bond collected) pairs with
   `reclaim_bonds`; `appeal` (bond collected) pairs with `lapse_appeal`
   (forfeit) or `recover_refund` (refund to appellant). A known,
   easy-to-miss fund-stranding pattern in appeal/re-adjudication flows is
   an outgoing adjudicator's bond getting silently overwritten without
   being credited first --
   `re_adjudicate` here explicitly credits the prior resolver's
   `RESOLVE_BOND` back before resetting `fixture_resolve_bond_returned`,
   proven by `test_appeal_then_re_adjudicate_reverses_verdict`'s
   assertion that the prior resolver has nothing left to reclaim
   afterward.
5. **Zero fee on any refund path**, confirmed by
   `test_inconclusive_full_refund_zero_fee` and
   `decisive_fee`/`finalize()` only ever running the fee split when
   `verdict in OUTCOMES`.
6. **Dust never gets stranded.** `compute_claim_payout`'s last-claimant
   remainder rule, proven with a deliberately indivisible 3-wei pool in
   `test_claim_payout_last_claimant_gets_dust`.
7. **`u256`/`Address` normalization.** Every address-keyed lookup
   (`get_position`, `get_positions`, `get_claimable`, the constructor's
   `treasury` arg) runs through `Address(x).as_hex`, matching the
   checksum-normalization lesson from prior GenLayer builds on this
   account (a caller-supplied differently-cased address silently missing
   its own position is a real, previously-confirmed rejection pattern).
8. **A decisive verdict with zero stakers on the winning outcome cannot
   strand the pot.** `finalize()` checks the winning outcome's own pool
   total, not just whether the verdict is a valid outcome; if nobody
   staked the side that actually won (a DRAW nobody bet on being the
   most likely real case), it settles INCONCLUSIVE -- full stake back to
   every bettor, zero fee -- instead of FINALIZED with an unclaimable
   distributable pot. Proven by
   `test_decisive_verdict_zero_stakers_on_winner_refunds_instead`.
9. **`resolve()`'s validator re-derivation runs through
   `gl.vm.spawn_sandbox`, not a bare second call.** A hand-rolled
   `run_nondet(leader_fn, validator_fn)` whose `validator_fn` calls
   `leader_fn()` again as a plain in-process Python call is
   architecturally identical to a pattern this account has previously
   observed live triggering GenVM's own `DETERMINISTIC_VIOLATION`
   protocol-level rejection, even when the two results genuinely
   matched. `validator_fn` here instead re-derives via
   `gl.vm.spawn_sandbox(leader_fn)` -- the same re-invocation mechanism
   `gl.eq_principle.strict_eq`'s own validator uses internally (confirmed
   by reading the installed SDK's `genlayer/eq_principle/__init__.py`
   directly), kept alongside the hand-rolled comparator (rather than
   switching outright to `strict_eq`) specifically because `strict_eq`'s
   bit-exact equality would reject on `sources`' own legitimately-varying
   `asof` field. **Not independently confirmed live** -- `resolve()` has
   not yet been called against a real fixture on the live deployment (see
   `docs/STATUS.md`); this closes the specific, previously-observed
   failure mode by construction but the fix itself is unverified against
   real GenVM consensus until a first live `resolve()` call succeeds.

## Known, accepted gap

`appeal()`'s bond amount is derived from the CURRENT decisive verdict's
own winning pool at the moment of the appeal call, not the pool at
`resolve()` time -- these are identical in every test here since betting
closes at kickoff and never changes again before `resolve()`, so this is
not a live discrepancy, just worth naming explicitly as an invariant this
design relies on (pools are frozen the instant `resolve()`'s
`RESOLVE_EARLIEST_OFFSET` guard passes, since `place_bet` already
requires `now < kickoff`).

## Portal-rejection checklist (applied, per this account's own accumulated history)

- **Provider binding**: publisher hosts/paths are hardcoded constants in
  `whistle_lib.PUBLISHER_REGISTRY`; `build_desk_url` never accepts a
  caller-supplied URL.
- **Validator independence**: `validator_fn` re-derives its own
  envelope from its own `sources_raw` fetch and compares the FULL
  derived triple, never trusting the leader's structural claim alone.
- **Checksum bugs**: covered above (item 7).
- **Nested nondeterminism**: exactly one top-level `gl.vm.run_nondet`
  call per method (`resolve`'s `_resolve_core`); `genvm-lint check`
  passes clean, confirming no nested-nondet violation.
- **Finality gating**: every pre-resolve view (`get_fixture`,
  `get_scoreline`, `get_record`) reads from committed `TreeMap` state
  only -- there is no "pending"/speculative read surface to gate.
- **Unsourced evidence**: `resolve()`'s leader closure only ever reads
  from the two locked desk URLs; no other data source is consulted.
- **No escape hatch**: `recover_refund` (7-day stall) and
  `lapse_appeal` (1-hour stall) both exist specifically so this doesn't
  happen; see the state-machine diagram in `docs/architecture.md`.
- **Single-candidate-verdict immunity**: N/A -- this is a 3-outcome
  market (`HOME`/`DRAW`/`AWAY`), not a single-candidate accept/reject
  gate.

## Second adversarial audit pass

A second, strict pass against this account's own consolidated
184-item pre-submission checklist (compiled from real prior steward
rejections and confirmed platform bugs across many earlier GenLayer
projects) found and fixed two real, code-level issues beyond the first
pass above: the zero-stakers-on-winner fund-stranding gap (item 8) and
the hand-rolled-validator consensus-rejection risk (item 9), both listed
above. It also found and fixed: a frontend gap where `claim()`/
`reclaim_bonds()`/`finalize()`/every other bond-paying write only waited
for GenVM's earlier "decided" state before declaring success, when an
EOA-directed value transfer only truly executes at FINALIZED
(`frontend/src/lib/whistle/sdk.ts`); an integration test that would have
failed on its first real run from passing `get_contract_factory` as a
pytest fixture instead of calling it directly; and documentation across
README/docs/the frontend that described an LLM extracting per-desk
facts, when the actual mechanism is a pure `gl.nondet.web.get` fetch plus
deterministic Python parsing with no LLM call anywhere in the contract.
Everything in this section has been fixed in the current source; see
`docs/STATUS.md` for whether a corresponding redeploy has landed.

## Third pass: live-endpoint verification

Both earlier passes reviewed the contract against its own source and
against a checklist. Neither ever fetched the two locked publisher
endpoints. Doing that turned up three defects that no amount of
source-level review could surface, because each is a mismatch between
the code and the outside world rather than an inconsistency inside the
code:

10. **`desk_a` could never produce a usable envelope.** The parser
    required `strStatus`, which TheSportsDB's free tier returns as
    `null` even for a match finished years ago. `_normalize_status("")`
    yielded `UNKNOWN`, so `usable` was always `False`. Fixed: an
    explicit status is honoured when present, and completion is
    otherwise inferred from a full integer scoreline with
    `strPostponed == "no"` -- safe only because `resolve()` cannot run
    until 105+ minutes after kickoff and desk_b must independently
    report the match finished.

11. **`desk_b` could never produce a usable envelope either.** The
    parser read `matchStatus`, `homeGoals`, `awayGoals` and
    `lastUpdate`. OpenLigaDB returns none of those keys; completion is
    the boolean `matchIsFinished` and goals live in `matchResults[]`.
    Fixed by reading the `After90Minutes` entry specifically, which also
    makes `RESULT_TYPE = "FT_90"` literally true -- the extra-time and
    penalties entries are excluded, so a shootout can never be mistaken
    for the full-time scoreline.

12. **The two desks were queried by one shared `fixture_id`, but their
    id spaces are unrelated.** `441613` is Liverpool vs Swansea on
    TheSportsDB and answers `No match with Id 441613 found!` -- plain
    text, not JSON -- on OpenLigaDB. Fixed: a fixture carries one
    reference per desk, each validated as a bare digit string so it
    cannot inject a path or query into a locked URL, both frozen at
    creation and exposed by `get_fixture`/`get_constitution` for
    independent audit.

Together these were fatal to the contract's central claim: every fixture
would have settled INCONCLUSIVE, and the two-desk agreement that the
whole design rests on could never fire. A fourth, related correction:
`COMPETITION` was `UCL_LP`, but OpenLigaDB carries German league
football only, so no UEFA fixture could ever have been present on both
desks. It is now `BL1`, the competition both desks actually cover.

Also fixed in this pass:

- `_fixture_view` returned a hardcoded `"UCL_LP"` rather than the
  `COMPETITION` constant, so it would have drifted regardless.
- `contracts/build_bundle.py` only **warned** when the bundle exceeded
  the 52,224-byte GenVM deploy ceiling, so CI would have passed an
  undeployable artifact. It now fails, and strips comments from the
  generated file (sources keep them), which also bought back headroom:
  48,603 bytes against 49,813 before.
- CI never ran `genvm-lint typecheck`, never ran the frontend linter,
  used `npm install` rather than `npm ci`, and never checked that the
  committed bundle matches what the source builds. All four are now
  enforced.

These changes alter contract logic and storage, so they require a
redeploy; see `docs/STATUS.md`.

### A regression this pass introduced, and caught

Stripping comments from the generated artifact (above) also stripped
`# type: ignore[misc]` from `evaluate_sources`, which is a pragma a tool
acts on rather than prose for a reader. `genvm-lint typecheck` then
reported a real `"None" is not iterable` against the bundle -- and the
first attempt at a CI gate did not catch it, because the tool's own
summary line is not usable as a signal:

- it labels every diagnostic severity `?`,
- it always prints `0 error(s), 0 warning(s)` regardless of what it
  found, and
- it exits non-zero whenever any diagnostic exists at all, which is
  always, since pyright emits one for every GenVM `Annotated` type
  (`u256`, `Address`) it believes is "not callable".

So the earlier "typecheck: 0 errors, 0 warnings" claim in this repo was
never evidence of anything. The gate now fails on any diagnostic other
than that known false-positive class, which is the only part of the
output that carries signal. It was tested both ways: it passes on the
current bundle and fails on a deliberately introduced diagnostic.

Both underlying problems are fixed: the bundler preserves pragma
comments (`type:`, `noqa`, `pyright:`, `pylint:`, `ruff:`, `mypy:`), and
`evaluate_sources` narrows its two reports explicitly so no suppression
is needed at all.

Note that `genvm-lint typecheck` runs pyright permissively -- it does not
report a `-> int` function returning `None`, for instance -- so it should
be read as a narrow check, not a full typecheck.
