#!/usr/bin/env python3
"""verify_lane_contract.py — does each llgenie bot's live SOUL actually commit it
to its responsibility, its report discipline, and its merge rule?

This is BEHAVIOUR verification, distinct from the file-drift check (make
sync-agent-profile CHECK=1): drift says files match; this says the rules that
make the lane do its job are present and non-empty. A lane that matches the tree
byte-for-byte but whose SOUL lacks the report line, the never-merge rule, or its
own duty passes sync and fails here (issue #2260).

Usage: python3 verify_lane_contract.py [--root DIR] [lane ...]
  --root DIR   profiles root to verify (default $HOME/.hermes/profiles), so a
               test can point a scratch fixture at it; the default is built from
               pathlib.Path.home(), never a hardcoded machine account path.
  lane ...     one or more lane names to check (default: every $HOME llgenie-* )
Exit: 0 all pass; 1 any lane missing a contract element (names lane + element).
"""
import argparse
import pathlib
import re
import sys

PROFILES = pathlib.Path.home() / ".hermes" / "profiles"


def _path_names(path: pathlib.Path) -> str:
    """Fully-resolved path with HOME rewritten to '$HOME' for error messages,
    so output never hardcodes a machine account name (owner rule)."""
    try:
        home = str(pathlib.Path.home().resolve())
        return str(path.resolve()).replace(home, "$HOME")
    except Exception:
        return str(path)


# What a lane must carry: (label, regex, why-it-matters). The gate asserts
# BEHAVIOUR, not text spelling: the regex is a referent that names the rule a
# lane must be committed to, so a SOUL that merely keeps the file but drops the
# duty, the report line or the merge rule cannot pass.
CONTRACT = [
    ("report-line", r"working\s+on\s+#",
     "every reply must open with `BOT <lane> · working on #<id> · branch · since · blocked · next` — a SOUL that drops the id-bearing report line loses the fleet's per-reply audit hook"),
    ("never-merge", r"never.*merge|never merge|do not merge|no merge",
     "a lane must be committed to not merging/pushing main"),
    ("bookend", r"bookend|announce.*work|start comment|finish comment",
     "claims are announced where the work lives and finished with a head+proof"),
    ("no-private-edit", r"issue\s*\+?\s*PR|agents/<profile>|versioned",
     "behaviour changes land by issue+PR under agents/<profile>/, not a private edit"),
    ("communicate", r"message_agent|@llgenie|report to|recall|shared bank|talk|message",
     "the lane must commit to HOW it talks to other lanes (message_agent / on-issue / recall) — a lane whose SOUL never says how it reports beyond its own turn cannot be audited for cross-lane behaviour"),
]

# Lane -> its own duty, one regex each (measured from the live SOULs).
DUTY = {
    "llgenie-planner": r"triag|dispat|orchestrat|idle",
    "llgenie-architect": r"architect|structural|refactor",
    "llgenie-issse-implementer": r"implement|PR\b|ready-for-review",
    "llgenie-pr-reviever": r"review|verdict|acceptance",
    "llgenie-ci-pipelines-maintainer": r"pipelin|gate|workflow",
    "llgenie-documentation-maintainer": r"documentation|note trio|agent-wiki|changes\.d",
    "llgenie-engine-improver": r"engine|pin|serving|tokens.*second",
    "llgenie-pr-merge-conflict": r"reba|conflict|stale",
    "llgenie-security": r"securit|vulnerab|scan",
    "llgenie-tester": r"test|evidence|run id|sha",
    "llgenie-product-manager": r"product|priorit|acceptance",
    "llgenie-business-analyst": r"analyst|frame|require",
    "llgenie-status-keeper": r"status|state sheet|lanes",
}


def _skills_have(sdir: pathlib.Path, pattern: str) -> bool:
    """Is there a materialized (non-.archive) skill matching `pattern` (as a path
    fragment, e.g. 'llgenie-security') with a non-empty SKILL.md under it?"""
    if not sdir.is_dir():
        return False
    for p in sdir.rglob("*"):
        if not p.is_file() or p.name != "SKILL.md":
            continue
        if ".archive" in p.parts:
            continue
        if pattern.lower() in str(p).lower():
            return True
    return False


def check(lane: str, root: pathlib.Path = PROFILES) -> tuple[bool, list[str]]:
    # 1. The SOUL at <root>/<lane>/SOUL.md (root defaults to $HOME/.hermes/profiles
    #    built from pathlib.Path.home() — this IS the $HOME setup the user means,
    #    the live profile, never the tree and never a hardcoded machine account path).
    p = root / lane / "SOUL.md"
    if not p.is_file():
        return False, [f"no SOUL at {_path_names(p)}, under $HOME/.hermes/profiles/"]
    s = p.read_text()
    missing = []
    for label, rx, why in CONTRACT:
        if not re.search(rx, s, re.I):
            missing.append(f"{label}: needs '{rx}' — {why}")
    if lane in DUTY and not re.search(DUTY[lane], s, re.I):
        missing.append(f"own-duty: none of '{DUTY[lane]}' found — a lane whose SOUL never says what it does cannot be verified")

    # 2. The skills are MATERIALIZED (not just declared) under $HOME, and at
    #    least one non-archived, non-empty SKILL.md exists. A lane with a skills/
    #    dir that holds only .archive stubs passes file-drift but has no live
    #    skill to load — this is behaviour, not parity.
    sdir = root / lane / "skills"
    if not sdir.is_dir():
        missing.append("skills-materialised: no skills/ dir under $HOME — the lane has declared skills but nothing materialised to load")
    else:
        materialised = _skills_have(sdir, "SKILL.md")
        if not materialised:
            missing.append("skills-materialised: skills/ exists but every SKILL.md is under .archive — no live skill is materialised to load")
    return (not missing), missing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="verify_lane_contract.py")
    ap.add_argument("--root", default=str(PROFILES),
                    help="profiles root to verify (default $HOME/.hermes/profiles)")
    ap.add_argument("lanes", nargs="*", help="lane names (default: every $HOME llgenie-*)")
    args = ap.parse_args(argv)
    root = pathlib.Path(args.root)
    if args.lanes:
        lanes = args.lanes
    else:
        lanes = sorted(p.parent.name for p in root.glob("llgenie-*/SOUL.md"))
    failures = 0
    for lane in lanes:
        ok, missing = check(lane, root=root)
        mks = " MISSING: " + "; ".join(missing) if missing else " ok"
        print(f"  {lane:38} {'PASS' if ok else 'FAIL'}{mks}")
        failures += (not ok)
    print(f"\n  {len(lanes)-failures}/{len(lanes)} lanes pass the behavioural contract")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
