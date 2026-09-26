"""
Bundle contracts/whistle_lib.py + contracts/Whistle.py into a single
deployable file at contracts/build/Whistle.deploy.py.

GenVM contracts are deployed as ONE source file -- sibling imports are not
supported by contract validation. whistle_lib.py is kept separate from
Whistle.py so its pure logic (the comparator, fee/payout math, adapters)
can be unit-tested directly with plain pytest, with no genlayer import
and no GenVM sandbox involved. Always lint/test the BUNDLED output, not
the two-file dev version, since the bundle is what actually ships.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent
LIB_PATH = ROOT / "whistle_lib.py"
CONTRACT_PATH = ROOT / "Whistle.py"
OUT_DIR = ROOT / "build"
OUT_PATH = OUT_DIR / "Whistle.deploy.py"

DEPENDS_RE = re.compile(r'^#\s*\{\s*"Depends"')


def strip_lib_module(text: str) -> str:
    lines = text.split("\n")
    out = []
    for line in lines:
        if line.strip() == "from __future__ import annotations":
            continue
        out.append(line)
    return "\n".join(out)


def strip_contract_module(text: str) -> str:
    lines = text.split("\n")
    out = []
    skip_import_block = False
    for line in lines:
        if DEPENDS_RE.match(line):
            continue
        if line.strip().startswith("from whistle_lib import ("):
            skip_import_block = True
            continue
        if skip_import_block:
            if line.strip() == ")":
                skip_import_block = False
            continue
        out.append(line)
    return "\n".join(out)


def main() -> None:
    header_line = CONTRACT_PATH.read_text(encoding="utf-8").split("\n", 1)[0]
    if not DEPENDS_RE.match(header_line):
        raise SystemExit(f"Whistle.py line 1 is not a Depends header: {header_line!r}")

    lib_src = strip_lib_module(LIB_PATH.read_text(encoding="utf-8"))
    contract_src = strip_contract_module(CONTRACT_PATH.read_text(encoding="utf-8"))

    # Nothing may come between the Depends header and real content -- some
    # GenVM runner-comment parsers reject a bundle with a comment block
    # directly here (confirmed on a prior project's live deploy attempt).
    # Comments elsewhere in the file (the section markers below) are fine.
    bundled = "\n".join([
        header_line,
        lib_src.strip("\n"),
        "# --- end whistle_lib.py ---",
        "",
        "# --- begin Whistle.py (GenVM contract) ---",
        contract_src.strip("\n"),
        "# --- end Whistle.py ---",
        "",
    ])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(bundled, encoding="utf-8", newline="\n")
    size = len(bundled.encode("utf-8"))
    print(f"Wrote {OUT_PATH} ({size} bytes)")
    limit = 52_224
    if size > limit:
        print(f"WARNING: {size} bytes exceeds the {limit}-byte deploy-size ceiling")
    else:
        print(f"OK: {size}/{limit} bytes ({size / limit:.1%} of ceiling)")


if __name__ == "__main__":
    main()
