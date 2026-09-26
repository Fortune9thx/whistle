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

## Not yet independently re-audited

This build has not yet had a second, adversarial audit pass distinct
from the author's own review above. Treat this section as the author's
self-assessment, not an external confirmation.
