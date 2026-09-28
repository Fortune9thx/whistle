# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- **The two publisher desks could never agree, so no fixture could ever
  settle decisively.** Verified against the live endpoints: TheSportsDB
  returns a null `strStatus` even for finished matches; OpenLigaDB has
  no `matchStatus`/`homeGoals`/`awayGoals` keys at all (completion is
  `matchIsFinished`, goals are in `matchResults[]` under
  `After90Minutes`); and the two services use unrelated id spaces, so a
  single shared `fixture_id` could not address the same match on both.
  A fixture now carries one validated reference per desk, and both
  parsers are written against captured live responses.
- `COMPETITION` is now `BL1` (Bundesliga). OpenLigaDB carries German
  league football only, so no `UCL_LP` fixture could ever have existed
  on both desks.
- `_fixture_view` returned a hardcoded `"UCL_LP"` instead of the
  `COMPETITION` constant.
- `contracts/build_bundle.py` now fails, rather than warning, when the
  bundle exceeds the 52,224-byte GenVM deploy ceiling, and strips
  comments from the generated artifact (sources keep them): 48,495
  bytes, down from 49,813.
- Frontend: bond sizes and the minimum kickoff lead are read from the
  live `get_config()` instead of being duplicated as literals; the
  time-derived action gates use a ticking clock rather than a
  render-time `Date.now()`, so a page left open across kickoff stops
  offering actions the contract will reject.
- `frontend/package-lock.json` carried a stale `name`, which breaks
  `npm ci`.

### Changed

- CI now runs `genvm-lint typecheck` and the frontend linter, installs
  with `npm ci` rather than `npm install`, and verifies the committed
  deploy bundle is exactly what the source builds.
- Test suite grew from 94 to 117, with both desks' real response shapes
  pinned by tests, including the plain-text 404 body OpenLigaDB returns
  for an unknown reference.

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
- Deployed live to Studio Next: `0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36`
  (see `deploy/deployments.json` for the superseded pre-audit-fix address).
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
