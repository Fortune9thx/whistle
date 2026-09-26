# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Initial WHISTLE contract (`contracts/Whistle.py` + `whistle_lib.py`):
  two-publisher FT scoreline agreement settled into a 1X2 pari-mutuel
  pool, with a full appeal/re-adjudicate/lapse/recover-refund lifecycle.
- 93 tests (45 pure-Python, 48 `gltest` direct-mode), `genvm-lint`
  clean.
- Frontend: marketing page + `/app` board, fixture ticket, create,
  portfolio, activity, docs.
- CI workflow running the full test suite + lint + frontend build on
  every push.
