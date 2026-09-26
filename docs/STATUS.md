# Status

| Surface | State |
|---|---|
| Contract tests | 93/93 passing (45 pure-Python `whistle_lib` + 48 `gltest` direct-mode) |
| `genvm-lint check` | passing, 3 checks |
| `genvm-lint typecheck` | 0 errors, 0 warnings |
| Bundle size | 48,492 / 52,224 bytes (92.9%) |
| GitHub | pending |
| Vercel | pending |
| Studio Next deploy | not attempted yet |

## Studio Next / Studio Dev, chain 61997

State resets on this network -- a redeploy is expected to produce a new
address, and prior transaction history is not durable. Nothing here is
mainnet.

## Deploy attempt log

Not yet attempted. This section will record, honestly: the exact
`Depends` hash probed, whether a minimal Hello contract's
`getContractSchemaForCode` call succeeded before spending any real GEN,
the real deploy transaction hash and its `txExecutionResultName` (not
just `statusName`/`lifecycle.outcome`, which can read `FINALIZED` even
for a reverted execution), and the resulting contract address or the
specific failure mode if it does not succeed. No GEN is spent on a real
deploy attempt without first running the free `getContractSchemaForCode`
probe.
