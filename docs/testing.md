# Testing

## Setup (Windows, this repo's pinned versions)

```bash
python -m pip install genlayer-test==0.30.0rc2 genvm-linter==0.11.1rc2
```

`genlayer-test` provides the `gltest` CLI/pytest plugin (direct-mode,
real GenVM sandbox execution -- not a mock of the contract's own logic).
`genvm-linter` provides `genvm-lint` (`check`, `typecheck`, `schema`,
`validate`).

## Running

```bash
python contracts/build_bundle.py           # regenerate contracts/build/Whistle.deploy.py
genvm-lint check contracts/build/Whistle.deploy.py
genvm-lint typecheck contracts/build/Whistle.deploy.py
pytest tests/direct/ -q
```

Always lint/test the bundled artifact (`contracts/build/Whistle.deploy.py`),
never the two-file dev source directly -- the bundle is what actually
gets deployed. Re-run `build_bundle.py` any time `Whistle.py` or
`whistle_lib.py` changes.

## Coverage map

- `tests/direct/test_whistle_lib.py` (45 tests) -- pure Python, zero
  `genlayer` import. Constitution validation, per-desk parsing, the 1X2
  derivation, `evaluate_sources`'s two-desk agreement gate,
  `is_well_formed_envelope`'s self-consistency check (the tests that
  would catch a lying leader), `compare_envelopes`'s equivalence check,
  fee/bond/payout math, pagination.
- `tests/direct/test_contract.py` (47 tests) -- real `gltest` direct-mode
  deploys against the actual bundled artifact: every state transition,
  every `UserError` guard, bond escrow/return/slash, decisive vs. refund
  payout, pagination, and one full appeal -> re_adjudicate ->
  reclaim_bonds cycle proving the prior resolver's bond isn't stranded.
- `tests/direct/test_smoke.py` (1 test) -- deploy + config sanity check.

## What direct-mode cannot exercise, and how that gap is covered

`gltest` direct-mode's `run_nondet` mock only ever invokes the leader
closure and returns its result directly -- it never invokes
`validator_fn`. `resolve()`'s independent-re-derivation/equivalence check
is therefore proven separately, with hand-constructed matching and
mismatched envelope pairs, in `test_whistle_lib.py`'s
`test_compare_envelopes_*` and `test_is_well_formed_rejects_lying_leader_*`
tests -- not inferred from `gltest` passing.

## CI

`.github/workflows/ci.yml` runs the unit suite, `gltest`, `genvm-lint
check`, and a frontend build on every push, pinned to the exact
locally-verified tool versions above.
