#!/usr/bin/env python3
"""Resolve the fleet-rules triple a stacked PR bumps into once rules 13/14 land.

`standing-rules.md` is the *canonical* source, so the base's copy wins outright — a branch's older copy is
drift, not an addition. `fleet-block-exemptions.json` is a *set of profiles*, so the resolution is the union
keyed by profile: dropping an entry silently re-fails a lane the list was written to tolerate, and keeping a
stale one is caught by the gate as STALE. A SOUL that the branch adds keeps its own text and gets its fleet
section regenerated from the canonical file, because only its owning lane may change anything else.
"""
import json
import pathlib
import re
import subprocess
import sys

H = "## Standing rules (fleet, learned 2026-10-28)"


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, cwd=sys.argv[1]).stdout


def base_version(path: str) -> str:
    return sh("git", "show", f"origin/feat/agent-profile-implementer-skill:{path}")


def canonical_block(repo: pathlib.Path) -> str:
    text = (repo / "agents/standing-rules.md").read_text()
    return H + "\n\n" + text.split(H, 1)[1].strip("\n")


def rewrite_block(soul: pathlib.Path, block: str) -> bool:
    lines = soul.read_text().splitlines()
    if H not in lines:
        return False
    s = lines.index(H)
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    soul.write_text("\n".join(lines[:s] + block.splitlines() + [""] + lines[e:]).rstrip("\n") + "\n")
    return True


def union_exemptions(repo: pathlib.Path) -> None:
    p = repo / "agents/fleet-block-exemptions.json"
    ours = json.loads(base_version("agents/fleet-block-exemptions.json"))
    try:
        theirs = json.loads(p.read_text())
    except json.JSONDecodeError:
        theirs = {"exemptions": []}
    seen = {e["profile"]: e for e in theirs.get("exemptions", [])}
    for e in ours.get("exemptions", []):
        seen.setdefault(e["profile"], e)
    merged = dict(ours)
    merged["exemptions"] = sorted(seen.values(), key=lambda e: e["profile"])
    p.write_text(json.dumps(merged, indent=2) + "\n")
    print(f"  exemptions: {len(merged['exemptions'])} profiles (union)")


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(
            "usage: resolve-fleet-triple.py <repo>\n"
            "  Resolves the standing-rules.md / fleet-block-exemptions.json / SOUL.md triple that a\n"
            "  stacked branch collides with once a rule lands: canonical file wins, exemptions union\n"
            "  by profile, fleet section regenerated. Run it in a worktree with conflicts staged.\n")
        return 2
    repo = pathlib.Path(sys.argv[1])
    conflicted = sh("git", "diff", "--name-only", "--diff-filter=U").split()
    print(f"  conflicted: {' '.join(conflicted)}")
    if "agents/standing-rules.md" in conflicted:
        (repo / "agents/standing-rules.md").write_text(base_version("agents/standing-rules.md"))
        print("  standing-rules.md: base copy (canonical source wins)")
    if "agents/fleet-block-exemptions.json" in conflicted:
        union_exemptions(repo)
    block = canonical_block(repo)
    for f in conflicted:
        if f.endswith("SOUL.md"):
            p = repo / f
            if p.exists() and rewrite_block(p, block):
                print(f"  {f}: fleet block regenerated from standing-rules.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
