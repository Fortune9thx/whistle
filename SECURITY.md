# Security

## Reporting

This is a testnet demo (Studio Next, chain 61997 -- state resets, no
mainnet value at risk). Open a GitHub issue at
[github.com/Fortune9thx/whistle](https://github.com/Fortune9thx/whistle/issues)
for anything found.

## Threat model and what's been checked

See [docs/audit.md](docs/audit.md) for the full adversary model, the
checked-and-confirmed-safe list (leader/validator independence, bond
escrow/disposal pairing, zero-fee refunds, dust handling, address
normalization, zero-stakers-on-winner fund-stranding), and a known,
accepted design invariant (`appeal()`'s bond sizing). Two adversarial
audit passes have been run against this contract; both are logged there
with what was found and fixed.

## Known limitations, disclosed rather than hidden

- **No LLM anywhere in this contract.** Consensus is a pure
  `gl.nondet.web.get` fetch against two locked, registry-defined
  publisher hosts, reconciled by deterministic Python parsing --
  `resolve()`'s non-determinism is "did two validators' own independent
  live fetches agree", not model sampling.
- **`resolve()`'s live consensus behavior is unverified.** `gltest`
  direct-mode cannot exercise `validator_fn` at all (it only ever invokes
  the leader closure), so the independent-re-derivation/equivalence
  check is proven with hand-constructed fixtures in
  `tests/direct/test_whistle_lib.py`, never via a real two-validator
  round. `resolve()` has not yet been called against a real fixture on
  the live deployment -- see `docs/STATUS.md`.
- **Publisher registry hosts are illustrative of the intended shape**,
  not verified-live integrations against each desk's real current API
  schema -- see `docs/architecture.md`'s registry section.
- **`treasury` is a plain EOA set once at deploy time**, not rotatable.
  A compromised deployer key controls where decisive-pot fees and
  slashed/forfeited bonds land, but never bettors' own principal (which
  always resolves to `gl.message.sender_address`, never a caller- or
  deployer-supplied field).
- **`APPEAL_WINDOW` (30 minutes) is this build's own chosen default**,
  not fixed by any external spec -- see `docs/architecture.md`.

## What we deliberately did not build

See the README's "What we refused" section -- no off-chain oracle
attestation, no raw-HTML `strict_eq`, no model-decided 1X2, no
per-match redeploys, no non-terminal state without a permissionless
escape hatch.
