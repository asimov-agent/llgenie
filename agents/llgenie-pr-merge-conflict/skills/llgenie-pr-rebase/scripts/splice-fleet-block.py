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


def rule_signature(line: str) -> str:
    """A rule line's identity, ignoring emphasis and trailing punctuation.

    Rules 13/14/15 carry no period inside the bold and rule 16 does; a signature that included the
    period would report every rule as changed on a punctuation fix. Compare on the first 40
    characters with markdown emphasis and trailing punctuation stripped.
    """
    core = line.strip().lstrip("-* ").replace("**", "").strip()
    return core[:40].rstrip(" .,:;").lower()


def rules_in(lines: list[str]) -> dict[str, str]:
    """Bold bullet rules in a section, keyed by signature."""
    out: dict[str, str] = {}
    for ln in lines:
        if re.match(r"^\s*[-*]\s+\*\*", ln):
            out[rule_signature(ln)] = ln
    return out


def main() -> int:
    force = "--force" in sys.argv[1:]
    block = canonical_block()
    soul = SOUL.read_text(encoding="utf-8")
    lines = soul.splitlines()
    head = "## Standing rules (fleet, learned 2026-10-28)"
    if head not in lines:
        sys.exit("SOUL has no fleet-block heading")
    s = lines.index(head)
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    existing = lines[s:e]
    new_section = block.splitlines()

    # NO-REGRESSION: refuse to replace a rule the source does not carry. Measured -- with the
    # historical /tmp source, this tool rewrote four standing rules to an OLDER generation on a
    # correct SOUL, and reported "block in soul: True" while doing it. A splice that silently
    # degrades the text it is meant to propagate is the same defect as a -X strategy resolution.
    lost = [ln for sig, ln in rules_in(existing).items() if sig not in rules_in(new_section)]
    if lost and not force:
        print("REFUSING: the rule source is older than this SOUL — it would drop "
              f"{len(lost)} rule(s):", file=sys.stderr)
        for ln in lost:
            print(f"    {ln.strip()[:110]}", file=sys.stderr)
        print("  Source: " + str(ISSUE), file=sys.stderr)
        print("  Update references/standing-rules.md, or pass --force if the removal is intended.",
              file=sys.stderr)
        return 1

    new = "\n".join(lines[:s] + new_section + [""] + lines[e:]).rstrip("\n") + "\n"
    if new != soul:
        SOUL.write_text(new, encoding="utf-8")

    # assert the authored text, not a paraphrase of it. Probe 16 was left on the RETIRED wording
    # ("Arm when done, and only on a base of main") after rule 16 was rewritten, so a correct SOUL
    # reported "rule 16: MISSING" and the tool looked broken. A probe naming text that no longer
    # exists is a false negative that trains the reader to ignore the check.
    for probe, label in (
        ("Never hold a PR without a remedy", "13"),
        ("Announce the work where the work lives", "14"),
        ("Start from a fresh upstream main", "15"),
        ("Arm auto-merge when the work is done", "16"),
    ):
        print(f"  rule {label}: {'present' if probe in new else 'MISSING'}")
    print(f"  block in soul: {block in new}")
    return 0 if block in new else 1


if __name__ == "__main__":
    sys.exit(main())
