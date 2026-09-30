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

## Third adversarial audit pass (2026-09-30)

Run against this account's checklist grown to 203 items (up from 184 at
the second pass), plus two new companion findings surfaced the same week
from other projects on this account. Findings, most severe first:

10. **[FIXED, CRITICAL] 5 of 10 `gl.chain.Event` subclasses had
    non-alphabetical positional (indexed) constructor parameters.**
    `gl.chain.Event._do_init` binds indexed fields by `zip(sorted(param
    names), positional values)` -- a declaration whose params are not
    already alphabetical silently records every value under the wrong
    field name, forever, on chain. Neither `genvm-lint` (warns only) nor
    `gltest` direct-mode (doesn't validate event emission at all) can
    catch this. `EventFixtureCreated`, `EventBetPlaced`, `EventResolved`,
    `EventAppealed`, and `Claimed` all had this bug; `EventFinalized` and
    the four single-field events did not (trivially or coincidentally
    alphabetical already). Fixed by reordering every affected class's
    `__init__` parameters to alphabetical order and updating each call
    site to match (`contracts/Whistle.py`). A permanent regression guard
    (`tests/direct/test_events.py`) now parses the bundle with `ast` and
    asserts every `gl.chain.Event` subclass has <=3 positional fields and
    that they're alphabetically ordered -- no `genlayer` import required,
    so it can never be skipped for toolchain reasons. This bug was live on
    the previously-deployed contract at the superseded address; the fresh
    deploy after this fix carries the correction (see `docs/STATUS.md`).
    Affects only event LOGS (off-chain observability) -- the frontend
    never reads contract events, only `.view()`/`.call()` state, so no
    on-chain STATE was ever affected by this bug, only what an external
    indexer would have seen.
11. **[VERIFIED NON-ISSUE] `gl.vm.run_nondet`'s `validator_fn` receiving a
    `Return`/`VMError` wrapper rather than the leader's raw value** (a
    real bug pattern that silently fails validators closed on other
    projects) does NOT affect WHISTLE: `_resolve_core`'s `validator_fn`
    already unwraps `leader_result.calldata` before `json.loads`
    (confirmed by direct re-read of the current source, not carried over
    from a prior audit's memory).
12. **[FIXED] Frontend transaction-success check used a blacklist that
    silently passes on a MISSING result field.**
    `submitWrite`'s `if (resultName && resultName !== "FINISHED_WITH_RETURN")
    throw` never fires when `resultName` is `undefined` -- a failed
    receipt fetch, a CANCELED/never-activated transaction, or any
    unexpected receipt shape would all be reported to the user as success
    with zero evidence. Fixed to a strict whitelist:
    `if (resultName !== "FINISHED_WITH_RETURN") throw`
    (`frontend/src/lib/whistle/sdk.ts`).
13. **[FIXED] CI's only lint gate (`genvm-lint check`) downloads the full
    pinned-runner tarball on every run and can fail on a cold GitHub
    Actions runner for reasons unrelated to the contract**, confirmed as a
    real, same-week finding on another project on this account.
    `genvm-lint lint` (AST-only, no SDK download) is now the required gate
    in `.github/workflows/ci.yml`; `check` remains as a
    `continue-on-error` best-effort step so a genuine schema-validation
    regression is still visible without being able to red the whole
    pipeline over tarball-hosting flakiness.
14. **[VERIFIED, no fix needed]** Checked and confirmed NOT applicable,
    each against a fresh read of the current code rather than assumed:
    adjudication-envelope-to-real-id binding (`is_well_formed_envelope`
    already rejects any `fixture_id` mismatch, and the envelope is built
    entirely from a closure-bound literal with no LLM/prompt step that
    could ever claim a different one); a locked source-key allowlist for
    the `sources` dict (N/A by construction -- `sources_raw` is populated
    solely by code iterating the fixed `DESK_IDS` tuple, so there is no
    caller- or leader-controlled path that could inject an unauthorized
    key); the fetch-vs-authenticate tradeoff (WHISTLE already implements
    the stronger option: code itself calls `gl.nondet.web.get` against a
    locked host+path registry, never asking a model to fetch on its own);
    an `isinstance(x, str)` guard that would reject an address arriving as
    an `Address` object instead of a string (no such guard exists on any
    address-shaped parameter, and the one address-typed argument that
    exists, the constructor's `treasury`, has already been empirically
    proven to survive exactly this arrival shape via a real, successful,
    read-back-confirmed live deploy); the single-file bundler silently
    dropping a spliced-region import (verified directly -- every real SDK
    import in both source files is present, byte for byte, in the
    rebuilt bundle; the only two lines the bundler removes are
    `from __future__ import annotations`, which cannot appear mid-file,
    and the now-redundant `from whistle_lib import (...)` block, both
    deliberate); the frontend's liveness banner collapsing an
    unresolved probe into a false "not deployed" (it already renders
    nothing while `state === "checking"`); and the liveness probe method
    itself (already `gen_getContractSchema`, never the EVM-only
    `eth_getCode`, which would misreport a live GenLayer contract as
    absent).

**Known, NOT closed by this pass -- the single largest remaining review
risk:** no payable write has ever been called against the live
contract (see `docs/STATUS.md`'s "Not done, and why"). `create_fixture`,
`place_bet`, `resolve`, `re_adjudicate`, `appeal`, `finalize`, `claim`,
`reclaim_bonds`, `cancel_fixture`, `expire_fixture`, and `recover_refund`
-- i.e. every write except nothing -- and with them the entire
`_Recipient(...).emit_transfer()` value-transfer mechanism the whole
economic design depends on, have only ever executed inside `gltest`'s
mocked direct-mode VM, never against the real GenVM runtime. A green test
suite proves the Python logic; it cannot prove a payable write actually
lands, that `gl.message.value` is read correctly at runtime, or that
`_Recipient(...).emit_transfer()` actually delivers GEN to a real EOA on
THIS specific deployment. Closing this requires either driving the
deployed frontend's real in-app wallet flow with a funded Studio Dev
account, or a `genlayer-js` script signing with a decrypted private key --
both require the operator's direct involvement and are deliberately not
attempted automatically.
