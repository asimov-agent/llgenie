#!/usr/bin/env python3
"""Fail the agent-image build when a lane declared in ``agents/manifest.json`` is missing.

The Hermes agent image (:file:`containers/agent/Dockerfile`) is the container every bot lane runs
in. Before issue #2181 it carried ZERO references to ``agents/`` or to profiles — the image had the
Hermes CLI but no lane, so whatever profile a job asked for resolved against an empty profile home.
This script is the half that makes the defect visible at BUILD time instead of inside a bot run.

It compares two real inputs the build provides:

* the ``agents/`` tree the Dockerfile COPYed into the image — its ``manifest.json`` DECLARES the
  lanes the fleet is supposed to hold;
* the profiles directory the build's install step wrote the lanes into (one
  ``<name>/`` home per manifest profile, mirroring ``$HERMES_HOME/profiles/<name>/``).

For every profile the manifest declares it requires that lane's home to actually be present with
its ``SOUL.md``. A lane the manifest declares but the image does not carry FAILS the build with the
missing lane named — the image the issue is about would otherwise ship a bot lane with no rulebook,
and that is the failure mode it exists to end. Wired into the Dockerfile's build ``RUN`` so a
missing lane stops the publish.

Issue #2669 deepened it: ``SOUL.md`` alone never proved the lane's OTHER behaviour landed. The gate
now also compares the lane's skills subtree — every ``SKILL.md`` the tree carries must exist in the
installed home and be byte-identical to it, so a lane that landed as rulebook-only (a `skills/`
subtree that failed to copy, or an installed skill that diverged from the tree) reds the build
naming the lane and the relative path.

Hermetic: reads only its two directory arguments — no network, no hermes, no home. The tests
(:file:`tests/test_agent_lanes_check.py`) drive this real script against fixture trees.

Exit codes: 0 all declared lanes installed, 1 a lane (or the manifest) is missing, 2 a required
argument is not even a directory — never a silent pass.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import sys
from pathlib import Path

PROFILES_SUBDIR = "profiles"  # the subdir under HERMES_HOME the install step writes lanes into


def _manifest_profiles(manifest: Path) -> list[str]:
    """The profile names the manifest declares, in manifest order."""
    data = json.loads(manifest.read_text())
    return [profile["name"] for profile in data.get("profiles", [])]


def findings(agents: Path, profiles: Path) -> list[str]:
    """Human-readable findings naming every declared lane the image does not carry.

    The manifest itself is data this gate must read, so a tree whose manifest is missing
    (or unparsable) is a finding too — an image with no declared lane set cannot be proven
    to hold the fleet, and the build must fail loudly rather than assume.
    """
    manifest = agents / "manifest.json"
    if not manifest.is_file():
        return [f"{agents.name}/manifest.json is missing — no lane set is declared, "
                "so the agent image cannot be proven to carry the fleet"]
    try:
        names = _manifest_profiles(manifest)
    except (json.JSONDecodeError, OSError, TypeError, KeyError) as exc:
        return [f"cannot read {agents.name}/manifest.json ({type(exc).__name__}: {exc}) — "
                "the declared lane set is unreadable, so the build cannot be verified"]
    missing: list[str] = []
    for name in names:
        soul = profiles / name / "SOUL.md"
        if not soul.is_file():
            missing.append(f"lane {name!r}: declared in {agents.name}/manifest.json but "
                           f"{profiles.name}/{name}/SOUL.md is absent — the agent image carries "
                           f"no {name} lane")
            continue
        missing.extend(_skill_findings(agents, name, profiles))
    return missing


def _skill_findings(agents: Path, name: str, profiles: Path) -> list[str]:
    """The skill-book half of a lane (issue #2669): every SKILL.md the tree carries must be present
    in the installed home and byte-identical to it. SOUL.md alone proved the rulebook landed, not
    the skillbooks; a lane installed with only its SOUL.md used to pass this gate while its bot ran
    without a single skill resolvable."""
    tree_skills = agents / name / "skills"
    if not tree_skills.is_dir():
        return []
    tree_files = [p for p in sorted(tree_skills.rglob("SKILL.md")) if p.is_file()]
    if not tree_files:
        return []
    inst_lane = profiles / name
    skill_dirs = sorted({md.parent.relative_to(tree_skills).as_posix() for md in tree_files})
    named = ", ".join(skill_dirs[:6]) + ("" if len(skill_dirs) <= 6 else ", …")
    if not (inst_lane / "skills").is_dir():
        return [f"lane {name!r}: the tree carries {len(tree_files)} SKILL.md file(s) under "
                f"agents/{name}/skills/ ({named}) but {profiles.name}/{name}/skills/ is absent — "
                f"the agent image carries the lane's rulebook without its skillbooks"]
    out: list[str] = []
    for md in tree_files:
        rel = md.relative_to(agents / name)
        target = inst_lane / rel
        if not target.is_file():
            out.append(f"lane {name!r}: {rel} is carried by agents/{name}/ but absent at "
                       f"{profiles.name}/{name}/{rel}")
        elif not filecmp.cmp(md, target, shallow=False):
            out.append(f"lane {name!r}: {rel} differs from the installed copy "
                       f"(tree {md.stat().st_size} b, image {target.stat().st_size} b)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "agent-lanes check").splitlines()[0])
    ap.add_argument("--agents", default="agents", metavar="DIR",
                    help="the agents/ tree the build COPYed in (must hold manifest.json). "
                         "default: agents")
    ap.add_argument("--profiles", default=None, metavar="DIR",
                    help="the directory the build INSTALLED the lanes into (one <name>/ per "
                         "manifest profile). default: $HERMES_HOME/profiles, else ~/.hermes/profiles")
    a = ap.parse_args(argv)

    agents = Path(a.agents)
    if not agents.is_dir():
        print(f"[agent-lanes] FAIL: --agents {agents} is not a directory — the agents tree that "
              "declares the lanes is missing, so the build cannot be checked", file=sys.stderr)
        return 2
    profiles = Path(a.profiles) if a.profiles else Path(os.environ.get(
        "HERMES_HOME", str(Path.home() / ".hermes"))) / PROFILES_SUBDIR

    items = findings(agents, profiles)
    if not items:
        declared = len(_manifest_profiles(agents / "manifest.json"))
        print(f"[agent-lanes] OK: all {declared} lane(s) declared in {agents.name}/manifest.json "
              f"are present in {profiles}, skills subtrees reconciled")
        return 0
    for item in items:
        print(f"[agent-lanes] FAIL: {item}", file=sys.stderr)
    print(f"[agent-lanes] FAIL: {len(items)} finding(s) against the declared lanes — a missing "
          "lane, a lane installed without its skills subtree, or a SKILL.md that differs from the "
          "tree — refusing a build that would run a lane with no rulebook or without its "
          "skillbooks", file=sys.stderr)
    return 1


def run_cli(argv: list[str] | None = None) -> int:
    """Run the gate, and make an unexpected abort unmistakable (issue #1134)."""
    try:
        return main(argv)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — an abort must never read as a pass
        print(f"[agent-lanes] FAIL: the gate aborted before finishing "
              f"({type(exc).__name__}: {exc}) — NOTHING was checked", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(run_cli())
