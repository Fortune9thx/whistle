# Status

| Surface | State |
|---|---|
| Contract tests | 94/94 passing (45 pure-Python `whistle_lib` + 49 `gltest` direct-mode) |
| `genvm-lint check` | passing, 3 checks |
| `genvm-lint typecheck` | 0 errors, 0 warnings |
| Bundle size | 48,492 / 52,224 bytes (92.9%) |
| GitHub | live -- [github.com/Fortune9thx/whistle](https://github.com/Fortune9thx/whistle) |
| Vercel | live -- [whistle-brown-ten.vercel.app](https://whistle-brown-ten.vercel.app) |
| Studio Next deploy | **live** -- `0x5A8d163887d18309751fe00b7459dAba1175D4A3` |

## Studio Next / Studio Dev, chain 61997

State resets on this network -- a redeploy is expected to produce a new
address, and prior transaction history is not durable. Nothing here is
mainnet.

## Deploy attempt log (2026-09-26)

1. **Free pre-check**: `deploy/probe_schema.mjs` ran `getContractSchemaForCode`
   against both `deploy/Hello.probe.py` (a trivial single-field contract,
   same pinned `Depends` hash) and the real bundle. Both resolved cleanly
   -- no gas spent, confirms the runner hash resolves on the live network
   right now.
2. **Hello probe, real deploy**: `deploy/Hello.probe.py` deployed via
   `genlayer deploy`, tx `0x90b65c3a8ca2f8924a1036b37cbc2db3cfff3db3f77e51638633619fe3282460`,
   `txExecutionResultName: FINISHED_WITH_RETURN`. Confirms the network is
   healthy for a basic constructor right now.
3. **WHISTLE, first real attempt: failed, but not a platform bug.**
   `--args '"0xADDR"'` (JSON-quoted, the pattern documented as correct in
   this account's own prior-project notes) produced `FINISHED_WITH_ERROR`.
   Root-caused by decoding the actual submitted calldata off the explorer
   API: the currently-installed `genlayer` CLI's `--args` parser only uses
   its `JSON.parse` result for object/array values, never for a plain
   scalar string -- so the JSON-quote characters were sent as literal
   characters embedded in the string, corrupting `Address(treasury)`.
   This is a real, reproducible CLI behavior (confirmed by reading
   `parseArg`/`parseScalar` in the installed `genlayer` package directly),
   not a repeat of the network-side "any non-trivial `__init__` fails"
   pattern documented on a prior project the day before.
4. **WHISTLE, second attempt: succeeded.** A **bare, unquoted** address
   argument (`--args 0xC6E6...4e537`) deploys cleanly -- the CLI's parser
   auto-detects a bare 40-hex-char value as its "address" calldata type,
   and GenVM correctly binds that to the contract's `treasury: str`
   parameter. Tx `0xe4fffeb8a952c52fb9e1f45adfbe1a8ca01e1101218b4adcc1e6c56ac4eba3a0`,
   `execution_result: SUCCESS`, `consensus_history.latestDecision.status:
   ACCEPTED`. Confirmed live and correct via `genlayer call ... get_config`
   and a second, independent read through `genlayer-js` directly -- both
   return the exact expected constitution, with `treasury` correctly
   checksummed to the deployer's own address.
5. **Frontend wired**: `VITE_CONTRACT_ADDRESS` set on Vercel production,
   redeployed. Live site shows the `live` banner with the real address and
   explorer link, `/app` board reads `total_fixtures: 0` (honest, no
   fixtures created yet -- no mock data), `/app/docs` reads live economics
   from the contract.

**Live contract**: `0x5A8d163887d18309751fe00b7459dAba1175D4A3`
(deployer/treasury: `0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537`, the
`bradbury-deploy` account already active on this machine). See
`deploy/deployments.json` for the full record including the exact
deployed bundle's sha256.

**Not done, and why**: no `create_fixture` call has been made against the
live contract. It is a payable write, and `genlayer write` cannot attach
GEN to a call at all (a confirmed CLI surface gap, not a protocol
limitation) -- exercising it requires either the in-app wallet flow or a
`genlayer-js` script signing with a decrypted private key, and no
keystore password was available to this session to do the latter safely.
Left to the in-app wallet flow, as the original build plan anticipated.
