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
   re-derives via `gl.vm.spawn_sandbox` rather than trusting the
   leader's claimed output.
3. **Then `tests/direct/test_whistle_lib.py`'s lying-leader tests**
   (`test_is_well_formed_rejects_lying_leader_verdict`,
   `test_compare_envelopes_rejects_lying_leader`). These are the tests
   that would fail if the contract ever trusted a leader-claimed verdict
   instead of recomputing it.
4. **Run it yourself:**
   ```bash
   python contracts/build_bundle.py
   genvm-lint lint contracts/build/Whistle.deploy.py
   genvm-lint check contracts/build/Whistle.deploy.py
   python -m pytest tests/direct/ -q
   ```
   Expect lint clean (3 checks, 23 methods) and all 97 tests green.
5. **Check `docs/STATUS.md`** for the current deployment state
   and live RPC confirmation.

---

## Core submission questions

### 1. What GenLayer decides
Given a locked fixture, GenLayer consensus resolves exactly one contested question: **Do two independent, locked publisher desks (`desk_a`, `desk_b`) agree on the identical full-time (FT) integer scoreline for the same completed 90-minute match?**
- There is **no LLM** involved anywhere in this contract. Consensus verifies live HTTP fetch agreement (`gl.nondet.web.get`) across validator nodes.
- Pure Python deterministic logic (`whistle_lib.derive_1x2`) maps the agreed scoreline into `HOME`, `DRAW`, or `AWAY`.
- If either desk is unavailable, still in progress (`LIVE`/`PRE`), reports different scores, or the resolution window expires without consensus, the market settles `INCONCLUSIVE` (100% principal refund, 0 fee).

### 2. Who loses GEN
- **Losing bettors**: Wallets that staked on an incorrect 1X2 outcome lose their stake to the winning pool.
- **Fixture creator**: Loses `CREATE_BOND` (0.05 GEN) slashed to the treasury only if the fixture reaches kickoff with zero bets placed (spam prevention).
- **Appellant**: Loses their appeal bond (floored at 0.05 GEN) slashed to the treasury if their appeal stalls past the lapse timeout without reversal.
- **Fees**: A 2% fee is taken from the decisive pot (split 50/50 between resolver and treasury) only on decisive outcomes. **Zero fees are charged on any refund or inconclusive resolution.**

### 3. Must-match vs. may-differ (Equivalence)
- **Must match exactly across both desks**: `status == "FT"`, integer `home_score`, integer `away_score`.
- **May differ freely**: `asof` timestamps, envelope JSON formatting, whitespace, provider-specific metadata, and surrounding fields. Only the extracted scoreline facts are compared.

### 4. Live contract & testnet reality
- **CURRENT Contract Address**: [`0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36`](https://explorer-studio-dev.genlayer.com/address/0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36)
- **Live Frontend App**: [whistle-brown-ten.vercel.app](https://whistle-brown-ten.vercel.app)
- **Chain**: Studio Dev / Studio Next (chain id `61997`, RPC `https://studio-dev.genlayer.com/api`).
- **Network honesty**: Studio Dev is an ephemeral development testnet. State resets are standard on this network; prior transactions may not persist indefinitely. Nothing here is mainnet.

### 5. Payable live status
- **Reads / Views**: 100% verified live via `gen_getContractSchema` and `genlayer call ... get_config` on CURRENT address `0xB7c5Ec5dc5d7A006Ef5dDE28E316E6A0586D4D36`.
- **Payable Writes (`create_fixture`, `place_bet`)**: Unproven live on-chain. The `genlayer` CLI write command does not support attaching GEN value (`--value` does not exist), and no private key was provided in this automated environment. The value transfer mechanism (`_Recipient.emit_transfer`) is verified through 48 direct-mode `gltest` sandbox tests. The intended execution path for live payable writes is through the live web app using an EIP-1193 browser wallet.

---

## What to push back on if you disagree

- The 30-minute `APPEAL_WINDOW` (docs/architecture.md) is this build's
  own choice, not spec-fixed -- if you'd rather it match one of the
  other named durations, that's a one-line constant change.
- The publisher registry's exact host/path pair per desk
  (`whistle_lib.PUBLISHER_REGISTRY`) is illustrative of the *shape* a
  locked registry takes, not a verified-live integration with a real
  licensed sports-data contract -- see the caveat in
  `docs/architecture.md`'s registry section.
