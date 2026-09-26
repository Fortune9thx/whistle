"""
Direct-mode test fixtures for WHISTLE.

`direct_vm`/`direct_deploy`/`direct_alice`/etc. are `genlayer-test`'s own
pytest fixtures (gltest.direct.pytest_plugin) -- no local reimplementation
needed.

Contract deploys always target the bundled single-file artifact
(contracts/build/Whistle.deploy.py), never the two-file dev version --
that bundle is what actually gets deployed to Studio Dev, so it is what
must be proven to lint/deploy/behave correctly. Run
`python contracts/build_bundle.py` before running these tests if
Whistle.py or whistle_lib.py changed.

One monkeypatch, never touching contract code: `os.unlink` on a temp file
the WASI mock still holds open via `os.dup2` raises `PermissionError` on
Windows only (harmless on POSIX) -- see genlayer-test-toolchain memory.

Known gap, not a contract bug: gltest direct-mode's `run_nondet` mock
only ever invokes the leader closure and returns its result directly --
it never invokes validator_fn, so resolve()'s independent-re-derivation/
equivalence check cannot be exercised end to end here. That logic
(whistle_lib.compare_envelopes, is_well_formed_envelope, evaluate_sources)
is instead unit-tested directly, with no genlayer import at all, in
tests/direct/test_whistle_lib.py.
"""
import os
import sys
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
sys.path.insert(0, str(CONTRACTS_DIR))

_orig_unlink = os.unlink


def _safe_unlink(path, *args, **kwargs):
    try:
        return _orig_unlink(path, *args, **kwargs)
    except PermissionError:
        pass


os.unlink = _safe_unlink

CONTRACT_PATH = str(CONTRACTS_DIR / "build" / "Whistle.deploy.py")

TREASURY_HEX = "0x00000000000000000000000000000000000000fe"


def to_hex(addr) -> str:
    """Normalize a create_address()/create_test_addresses() value (a real
    Address, or a raw 20-byte fallback) to a hex string."""
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    if isinstance(addr, (bytes, bytearray)):
        return "0x" + addr.hex()
    return str(addr)
