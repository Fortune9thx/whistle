# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Initial WHISTLE contract (`contracts/Whistle.py` + `whistle_lib.py`):
  two-publisher FT scoreline agreement settled into a 1X2 pari-mutuel
  pool, with a full appeal/re-adjudicate/lapse/recover-refund lifecycle.
- 94 tests (45 pure-Python, 49 `gltest` direct-mode), `genvm-lint`
  clean.
- Frontend: marketing page + `/app` board, fixture ticket, create,
  portfolio, activity, docs.
- CI workflow running the full test suite + lint + frontend build on
  every push.
- Deployed live to Studio Next: `0x5A8d163887d18309751fe00b7459dAba1175D4A3`.
- `SECURITY.md`.

### Fixed

- A decisive verdict with zero stakers on the winning outcome (e.g. a
  DRAW nobody bet on) no longer finalizes with an unclaimable pot --
  `finalize()` now checks the winning outcome's own pool and settles
  INCONCLUSIVE (full refund, zero fee) when it's empty.
- `resolve()`'s validator now re-derives its independent answer via
  `gl.vm.spawn_sandbox`, not a bare second call -- closes a live GenVM
  consensus-rejection risk this account has previously observed from a
  hand-rolled validator pattern.
- Frontend write confirmation now waits for true `FINALIZED`, not the
  earlier `decided` state, for every write that moves GEN out of the
  contract (`claim`, `reclaim_bonds`, `finalize`, and every bond/escape
  path).
- Fixed an integration test that would have failed on first run
  (`get_contract_factory` passed as a pytest fixture instead of called
  directly).
- Added baseline security headers (`X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`) to the deployed frontend.
- Corrected documentation that described an LLM extracting per-desk
  facts -- the actual mechanism is a pure `gl.nondet.web.get` fetch plus
  deterministic Python parsing; no LLM is called anywhere in the
  contract.
