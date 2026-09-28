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
import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).parent
LIB_PATH = ROOT / "whistle_lib.py"
CONTRACT_PATH = ROOT / "Whistle.py"
OUT_DIR = ROOT / "build"
OUT_PATH = OUT_DIR / "Whistle.deploy.py"

DEPENDS_RE = re.compile(r'^#\s*\{\s*"Depends"')

# Comments a tool acts on, not prose for a reader. Stripping these would
# silently change how the artifact typechecks or lints, so they stay.
PRAGMA_RE = re.compile(r"^#\s*(type:|noqa|pyright:|pylint:|ruff:|mypy:)")


def strip_comments(text: str) -> str:
    """Drop comment tokens from the bundled artifact.

    The two source files carry the explanatory comments -- why each desk
    is parsed the way it is, which GenVM behaviours forced which choice --
    and those are what a reader should review. Repeating all of it inside
    the single deployed file costs several KB against a hard 52,224-byte
    GenVM deploy ceiling and buys nothing on-chain, so the artifact ships
    without them. Docstrings are kept: they are real objects, not
    comments, and removing them could change behaviour.

    Tokenising (rather than matching '#' per line) is what makes this
    safe -- a '#' inside a string literal is not a comment.
    """
    out = []
    prev_end = (1, 0)
    prev_type = None
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        tok_type, tok_str, start, end, _ = tok
        if tok_type == tokenize.COMMENT and not PRAGMA_RE.match(tok_str.strip()):
            prev_end = end
            prev_type = tok_type
            continue
        # A NL that only terminated a now-removed comment would leave a
        # blank line behind; drop it so stripping cannot grow the file.
        if tok_type == tokenize.NL and prev_type == tokenize.COMMENT:
            prev_end = end
            prev_type = tok_type
            continue
        if start[0] > prev_end[0]:
            out.append("\n" * (start[0] - prev_end[0]))
            out.append(" " * start[1])
        elif start[1] > prev_end[1]:
            out.append(" " * (start[1] - prev_end[1]))
        out.append(tok_str)
        prev_end = end
        prev_type = tok_type
    return "".join(out)


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

    # The Depends header is a runner directive, not a comment to strip.
    stripped_body = strip_comments(bundled.split("\n", 1)[1])
    bundled = header_line + "\n" + stripped_body.strip("\n") + "\n"

    compile(bundled, str(OUT_PATH), "exec")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(bundled, encoding="utf-8", newline="\n")
    size = len(bundled.encode("utf-8"))
    print(f"Wrote {OUT_PATH} ({size} bytes)")
    limit = 52_224
    if size > limit:
        # Hard failure, not a warning: a bundle over the ceiling cannot be
        # deployed at all, so letting the build (and CI) pass would just
        # defer the discovery to a gas-costing deploy attempt.
        raise SystemExit(
            f"FAIL: {size} bytes exceeds the {limit}-byte GenVM deploy ceiling "
            f"by {size - limit}"
        )
    print(f"OK: {size}/{limit} bytes ({size / limit:.1%} of ceiling)")


if __name__ == "__main__":
    main()
