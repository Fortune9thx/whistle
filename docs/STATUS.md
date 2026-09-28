# Status

| Surface | State |
|---|---|
| Contract tests | 117/117 passing (68 pure-Python `whistle_lib` + 49 `gltest` direct-mode) |
| `genvm-lint check` | passing, 3 checks |
| `genvm-lint typecheck` | 0 errors, 0 warnings |
| Bundle size | 48,495 / 52,224 bytes (92.9%) |
| GitHub | live -- [github.com/Fortune9thx/whistle](https://github.com/Fortune9thx/whistle) |
| Vercel | live -- [whistle-brown-ten.vercel.app](https://whistle-brown-ten.vercel.app) |
| Studio Next deploy | `0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36` -- live, but **superseded by pending redeploy** (see below) |

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
6. **Redeploy (2026-09-27)** after a second, strict adversarial audit
   pass found and fixed two real contract-level issues (see
   `docs/audit.md` items 8-9: a zero-stakers-on-winning-outcome
   fund-stranding gap in `finalize()`, and `resolve()`'s validator
   switched from a bare second call to `gl.vm.spawn_sandbox`). The
   original address above could not be patched in place -- redeployed
   fresh via the same probe-first protocol (free schema check, then a
   real deploy), confirmed live the same way (`execution_result:
   SUCCESS`, `get_config()` reads correctly), tx
   `0xd29a871789527d6a716055cbe591b55cad07b78b17e8f7d5c50da5a79e5f2245`.
   Every reference to the contract address across README/STATUS/Vercel
   has been updated to the new one below -- see
   `deploy/deployments.json` for the full, superseded-vs-current record.

**Live contract**: `0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36`
(deployer/treasury: `0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537`, the
`bradbury-deploy` account already active on this machine). See
`deploy/deployments.json` for the full record including the exact
deployed bundle's sha256.

## Pending redeploy (blocking a decisive live settlement)

A live-endpoint audit found that the contract as deployed at
`0xB7c5...4D36` **can never reach a decisive verdict**, for three
independent reasons, each confirmed against the real APIs:

1. `desk_a`'s parser required `strStatus`, which TheSportsDB's free tier
   returns as `null` even for a match finished in 2014 -- so desk_a was
   never usable.
2. `desk_b`'s parser read `matchStatus`/`homeGoals`/`awayGoals`/
   `lastUpdate`; OpenLigaDB returns `matchIsFinished`, `matchResults[]`
   (`After90Minutes` -> `pointsTeam1`/`pointsTeam2`) and
   `lastUpdateDateTime`. None of those keys existed in its responses --
   so desk_b was never usable either.
3. Both desks were queried by one shared `fixture_id`, but their id
   spaces are unrelated: `441613` is Liverpool vs Swansea on TheSportsDB
   and answers `No match with Id 441613 found!` -- as plain text, not
   JSON -- on OpenLigaDB.

Every fixture on the deployed contract would therefore settle
INCONCLUSIVE, always. All three are fixed in source: a fixture now
carries one validated reference per desk, both parsers are written
against captured live responses, and the competition is the Bundesliga
(the only one both desks carry). The fix changes contract logic and
storage, so it **requires a redeploy** -- a live GenVM contract cannot be
patched in place.

Bundle ready to deploy: `sha256:e475c7f5f31746551ceab20a74e3a42fa51c75e6d26c4eef7689232857ab45ba`,
48,495 / 52,224 bytes, `genvm-lint check` + `typecheck` clean,
117/117 tests green, and the free `getContractSchemaForCode` probe
against Studio Next resolves it with `create_fixture` carrying
`desk_a_ref`/`desk_b_ref`.

Redeploy with the same probe-first protocol already documented below:

```bash
python contracts/build_bundle.py
node deploy/probe_schema.mjs contracts/build/Whistle.deploy.py   # free
genlayer deploy --contract contracts/build/Whistle.deploy.py \
  --args 0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537              # bare, unquoted
```

Then set `VITE_CONTRACT_ADDRESS` on Vercel to the new address, redeploy
the frontend, and add the new entry to `deploy/deployments.json`.

**Not done, and why**: no `create_fixture` call has been made against the
live contract. It is a payable write, and `genlayer write` cannot attach
GEN to a call at all (a confirmed CLI surface gap, not a protocol
limitation) -- exercising it requires either the in-app wallet flow or a
`genlayer-js` script signing with a decrypted private key, and no
keystore password was available to this session to do the latter safely.
Left to the in-app wallet flow, as the original build plan anticipated.
