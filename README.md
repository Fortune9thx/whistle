# WHISTLE

WHISTLE settles one object on-chain: the full-time 90-minute scoreline of a locked football fixture, agreed by two independent, locked publisher desks.

- **Live:** [whistle-brown-ten.vercel.app](https://whistle-brown-ten.vercel.app) -- marketing + app, wired to the live contract below.
- **Address:** [`0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36`](https://explorer-studio-dev.genlayer.com/address/0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36) on Studio Next (chain 61997). See [docs/STATUS.md](docs/STATUS.md) for the full deploy log.
- **GitHub:** https://github.com/Fortune9thx/whistle

## What GenLayer decides

Given a locked fixture (same `fixture_id`, both desks published a completed **FT** result -- not `LIVE`, not a preview), GenLayer's consensus owns exactly one contested judgment call: **do the two locked desks agree on the same integer scoreline for the same completed match?** Each validator independently fetches both locked desk URLs itself (no LLM is involved anywhere in this contract -- the non-determinism is purely "did two validators' own live HTTP fetches agree", via `gl.vm.run_nondet`/`gl.vm.spawn_sandbox`); code alone then maps the agreed scoreline to a 1X2 verdict. No party ever claims a bare `HOME`/`DRAW`/`AWAY` value that the contract trusts directly -- see docs/architecture.md for how `verdict_1x2` is always recomputed from `scoreline`, never read as anyone's claim.

## Adversary

A leader node (honest or compromised) that fabricates a scoreline, a stale desk still reporting `LIVE`/`PRE` past the point a match should be over, one desk down or timing out, two desks reporting genuinely different final scores, or a caller trying to bet after kickoff or resolve before the match could plausibly be finished.

## Must agree vs. may differ

**Must match exactly, both desks:** `status == "FT"`, integer `home`/`away` goals. **May differ freely:** each desk's own `asof` timestamp, response envelope shape, and any surrounding prose/HTML -- only the derived `(status, home, away)` facts are ever compared. See `whistle_lib.compare_envelopes`.

## Failure policy

Anything short of two matching FT scorelines -- one desk still `LIVE`/`PRE`, a desk reporting `POSTPONED`/`ABANDONED`, a genuine score conflict between the two desks, or the 36-hour outer window lapsing with nobody resolving -- settles `INCONCLUSIVE`: every bettor gets their own stake back in full, zero fee, no winner side. WHISTLE never picks a side under uncertainty.

## Economics

- 1 GEN minimum bet, one outcome per wallet, top-ups on the same side only.
- `CREATE_BOND` 0.05 GEN, slashed to treasury only if a fixture reaches kickoff with zero bets ever placed.
- `RESOLVE_BOND` 0.02 GEN, always returned to whoever called `resolve()`/`re_adjudicate()`, plus a fee share when the outcome is decisive.
- Fee: 2% of the decisive pot, split 50/50 between the resolver and the treasury. **Zero fee on any refund.**
- Appeal bond: 50% of the decisive pool, floored at 0.05 GEN. Grounds: `SCORE`, `STATUS`, `FIXTURE`, `REVISED`.
- Escape hatches: a stalled appeal lapses back to the prior verdict after 1 hour; a fixture stuck in any non-terminal state for 7 days after kickoff can be forced to a full, fee-free refund by anyone via `recover_refund`.

## Methods

Full API in [docs/architecture.md](docs/architecture.md). Writes: `create_fixture`, `place_bet`, `resolve`, `finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_fixture`, `expire_fixture`, `claim`, `recover_refund`, `reclaim_bonds`.

## Tests

97 tests: 45 pure-Python (`whistle_lib`, no `genlayer` import -- the comparator, fee/payout math, envelope self-consistency) + 48 `gltest` direct-mode (real GenVM sandbox deploy + full state-machine execution) + 1 `test_smoke` + 3 `test_events` (static AST event declaration guards). `genvm-lint check`/`typecheck` both pass on the bundled artifact. See [docs/testing.md](docs/testing.md).

## Network

Studio Next / Studio Devnet, chain id **61997**, `https://studio-dev.genlayer.com/api`. **State resets** -- this is a preview network, not a durable mainnet. A `not deployed` or `no code at this address` banner in the frontend means exactly that: check docs/STATUS.md, don't assume the app is broken.

## What we refused

- **A cron job or off-chain oracle as ground truth.** Every scoreline is fetched and cross-checked live, on-chain, by GenVM consensus at resolve time -- never pre-computed and merely attested.
- **Raw-HTML `strict_eq` on either desk's response.** Both locked desks are JSON; `asof`/markup/whitespace are explicitly excluded from the comparison so cosmetic drift between two honest fetches never causes a false reject.
- **The model deciding 1X2.** It is only ever asked to extract structured per-desk facts; `derive_1x2` is a pure, auditable, three-line function in `whistle_lib.py`.
- **One contract per match.** A single factory-style contract holds every `UCL_LP` fixture -- no per-match redeploy.
- **A 0% "no closer" design.** Every non-terminal path (stalled appeal, unresolved fixture, zero-bet fixture) has an explicit, permissionless escape hatch; nothing can get stuck forever waiting on one specific actor.

## License

MIT -- see [LICENSE](LICENSE).
