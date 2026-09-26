# Steward brief

For anyone reviewing this build for a GenLayer portal submission, in one
pass:

1. **Read `contracts/whistle_lib.py` first**, not the contract. Zero
   `genlayer` import, plain pytest. It's where the actual judgment call
   -- two-desk agreement, 1X2 derivation, fee/payout math -- lives, and
   it's the part worth scrutinizing hardest.
2. **Then `contracts/Whistle.py`'s `_resolve_core`**, the only method
   that calls `gl.vm.run_nondet`. Confirm `leader_fn` only ever reads
   from `build_desk_url`'s two locked hosts, and that `validator_fn`
   calls `leader_fn()` again itself rather than only re-checking the
   leader's own claimed output.
3. **Then `tests/direct/test_whistle_lib.py`'s lying-leader tests**
   (`test_is_well_formed_rejects_lying_leader_verdict`,
   `test_compare_envelopes_rejects_lying_leader`). These are the tests
   that would fail if the contract ever trusted a model-claimed verdict
   instead of recomputing it.
4. **Run it yourself:**
   ```
   python contracts/build_bundle.py
   genvm-lint check contracts/build/Whistle.deploy.py
   pytest tests/direct/ -q
   ```
   Expect lint clean and every test green. See `docs/architecture.md`
   for the two places this build's contract code deliberately diverges
   from a literal reading of the original brief, and why.
5. **Check `docs/STATUS.md`** for the current, honest deployment state
   before assuming any address in this repo is live.

## What to push back on if you disagree

- The 30-minute `APPEAL_WINDOW` (docs/architecture.md) is this build's
  own choice, not spec-fixed -- if you'd rather it match one of the
  other named durations, that's a one-line constant change.
- The publisher registry's exact host/path pair per desk
  (`whistle_lib.PUBLISHER_REGISTRY`) is illustrative of the *shape* a
  locked registry takes, not a verified-live integration with a real
  licensed sports-data contract -- see the caveat in
  `docs/architecture.md`'s registry section.
