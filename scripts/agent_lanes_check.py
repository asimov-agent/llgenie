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

Hermetic: reads only its two directory arguments — no network, no hermes, no home. The tests
(:file:`tests/test_agent_lanes_check.py`) drive this real script against fixture trees.

Exit codes: 0 all declared lanes installed, 1 a lane (or the manifest) is missing, 2 a required
argument is not even a directory — never a silent pass.
"""

from __future__ import annotations

import argparse
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
    return missing


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
              f"are present in {profiles}")
        return 0
    for item in items:
        print(f"[agent-lanes] FAIL: {item}", file=sys.stderr)
    print(f"[agent-lanes] FAIL: {len(items)} lane(s) declared in agents/manifest.json are missing "
          "from the image — refusing a build that would run a lane with no rulebook", file=sys.stderr)
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
