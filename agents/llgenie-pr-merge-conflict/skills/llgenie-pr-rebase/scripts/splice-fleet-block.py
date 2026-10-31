#!/usr/bin/env python3
"""Splice the canonical fleet fence from #873 into a lane SOUL — copy, never retype.

Punctuation is load-bearing: rules 13/14/15 have no period inside the bold, rule 16 does, and a copy that
"fixes" that fails `block in soul` on punctuation alone (#972). So the block is extracted verbatim from the
issue body and asserted present afterwards, rather than rewritten by hand.
"""
import os
import pathlib
import re
import sys

# The standing-rules source. Historically pinned to a /tmp scratch file, which does not exist on
# any other machine or after a reboot -- so the script failed for every reader but its author.
# Resolve it: $REBASE_STANDING_RULES, else the versioned reference beside the SKILL, else the
# historical scratch path.
def _standing_rules() -> pathlib.Path:
    env = os.environ.get("REBASE_STANDING_RULES")
    if env:
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve().parent.parent / "references" / "standing-rules.md"
    if here.is_file():
        return here
    return pathlib.Path("/tmp/873.md")


ISSUE = _standing_rules()
if len(sys.argv) < 2:
    sys.stderr.write(
        "usage: splice-fleet-block.py <SOUL.md>...\n"
        "  Regenerates the fleet standing-rules block in each given file from the canonical\n"
        "  rules. Override the rules source with $REBASE_STANDING_RULES.\n")
    raise SystemExit(2)
SOUL = pathlib.Path(sys.argv[1])


def canonical_block() -> str:
    text = ISSUE.read_text(encoding="utf-8")
    # the first fenced block that opens the standing-rules heading
    m = re.search(r"^```\n(## Standing rules \(fleet, learned 2026-10-28\)\n.*?)^```$", text, re.S | re.M)
    if not m:
        sys.exit("could not find the canonical fence in the issue body")
    return m.group(1).rstrip("\n")


def main() -> int:
    block = canonical_block()
    soul = SOUL.read_text(encoding="utf-8")
    lines = soul.splitlines()
    head = "## Standing rules (fleet, learned 2026-10-28)"
    if head not in lines:
        sys.exit("SOUL has no fleet-block heading")
    s = lines.index(head)
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    new = "\n".join(lines[:s] + block.splitlines() + [""] + lines[e:]).rstrip("\n") + "\n"
    SOUL.write_text(new, encoding="utf-8")

    # assert the authored text, not a paraphrase of it
    for probe, label in (
        ("Never hold a PR without a remedy", "13"),
        ("Announce the work where the work lives", "14"),
        ("Start from a fresh upstream main", "15"),
        ("Arm when done, and only on a base of `main`", "16"),
    ):
        print(f"  rule {label}: {'present' if probe in new else 'MISSING'}")
    print(f"  block in soul: {block in new}")
    return 0 if block in new else 1


if __name__ == "__main__":
    sys.exit(main())
