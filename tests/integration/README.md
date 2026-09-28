# Integration tests (live Studio Next)

`tests/direct/` (117 tests, all green, no network needed) covers every
deterministic guard and state transition, plus the full leader/validator
equivalence comparator as pure-Python unit tests. It cannot prove two
things `gltest` direct-mode structurally cannot exercise:

1. **Real GenVM consensus on `gl.vm.run_nondet`** -- direct-mode's WASI
   mock only ever invokes the leader closure once and returns its result
   directly; it never invokes `validator_fn` or simulates a multi-
   validator round. Whether real validators, each independently fetching
   the same two locked desks, actually reach agreement (or correctly
   disagree) can only be observed live.
2. **Real HTTP behavior from the two locked publisher desks** --
   direct-mode tests feed `gl.nondet.web.get` from `mock_web`, not the
   real internet. A desk changing its response shape, rate-limiting, or
   reporting a genuinely ambiguous in-progress state is only visible
   against the real network.

## Prerequisites

- `genlayer network set studio-dev` (or the account already configured
  for chain 61997, RPC `https://studio-dev.genlayer.com/api`).
- A **funded** Studio Next account. Budget at least `CREATE_BOND` (0.05)
  + `RESOLVE_BOND` (0.02) + `MIN_BET` (1) per fixture exercised, plus
  real transaction fees.
- `.env` in the repo root (gitignored) with `DEPLOYER_PRIVATE_KEY=0x...`.
- Studio Next **resets state periodically** -- a fixture created in one
  run will not exist in a later one. Integration tests always deploy a
  fresh contract instance per run; never hardcode a fixture id or
  contract address from a prior run.

## Running

```bash
gltest tests/integration -v
```

Do **not** run these with plain `pytest` -- `gltest`'s own CLI wires up
`gltest.config.yaml`'s network config; plain `pytest` has no RPC endpoint
to talk to. CI runs `tests/direct` only (no funded key available there),
exactly like every other GenLayer project on this account.

## Known live-network characteristics to expect, not treat as bugs

- `waitForTransactionReceipt({status: FINALIZED})` can time out on a
  genuinely successful write; check `txExecutionResultName` via
  `getTransaction()` instead of trusting a timeout as failure.
- A `FINALIZED`/`ACCEPTED` status is not itself proof of a successful
  execution -- always check `txExecutionResultName ==
  "FINISHED_WITH_RETURN"` before treating a write as having actually
  succeeded, per `docs/STATUS.md`'s deploy attempt log.
- `eth_getCode` returns `0x` for a live, working GenLayer intelligent
  contract -- it is not an EVM contract. Use `gen_getContractSchema` for
  liveness checks (see `frontend/`'s network probe).
