#!/usr/bin/env python3
"""Prove the agent image carries every profile the manifest declares (issue #2934).

`publish-agent-image.yml` builds + pushes `llgenie/agent`, but until now it never *ran* the image
it published. Measured on main `81e6de6e8` (2026-11-19): the published `agent:latest` answered
`make hermes-smoke` with `Profile 'llgenie-status-keeper' does not exist` — a publish can therefore
push an image whose lane provisioning silently landed nowhere, and the next live bot run is what
discovers it.

This seam is the command the agent leg runs INSIDE the just-booted image (the leg boots it the
standard way: scrubbed_run + $(AGENT_SHELL_FORWARD) + $(AGENT_BOT_MARKER), repo mounted at /repo).
For every lane named in `agents/manifest.json`, it tests the exact path Hermes resolves a
`-p <lane>` profile from — `$HERMES_HOME/profiles/<lane>/config.yaml`, the image's own filesystem
and its own HERMES_HOME. Each lane prints `OK <lane>` or `MISSING <lane>`; any missing lane
exits 1 naming it. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def manifest_lanes(path: Path) -> list[str]:
    """The lane names agents/manifest.json declares — the truth this check compares against."""
    data = json.loads(path.read_text())
    profiles = data.get("profiles") if isinstance(data, dict) else data
    if not isinstance(profiles, list) or not profiles:
        raise SystemExit(f"[profiles-check] manifest unusable: {path} declares no profiles list")
    lanes = [p["name"] if isinstance(p, dict) else p for p in profiles]
    if any(not isinstance(n, str) or not n for n in lanes):
        raise SystemExit(f"[profiles-check] manifest unusable: {path} has a profile without a name")
    return lanes


def profile_path(home: Path, lane: str) -> Path:
    """Where Hermes resolves `-p <lane>`: profiles/<lane>/config.yaml under HERMES_HOME."""
    return home / "profiles" / lane / "config.yaml"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default="agents/manifest.json", help="lane roster source")
    ap.add_argument("--home", default=None,
                    help="profile home to test (default: $HERMES_HOME, then ~/.hermes)")
    args = ap.parse_args(argv)

    lanes = manifest_lanes(Path(args.manifest))
    home = Path(args.home) if args.home else Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    print(f"[profiles-check] checking {len(lanes)} manifest lanes under {home}", flush=True)

    missing: list[str] = []
    for lane in lanes:
        if profile_path(home, lane).is_file():
            print(f"[profiles-check] OK {lane}", flush=True)
        else:
            print(f"[profiles-check] MISSING {lane}", flush=True)
            missing.append(lane)

    if missing:
        print(
            f"[profiles-check] FAILED: {len(missing)}/{len(lanes)} manifest lanes have no "
            f"profile config at {home}/profiles/<lane>/config.yaml: {', '.join(missing)}",
            flush=True,
        )
        return 1
    print(f"[profiles-check] OK: all {len(lanes)} manifest lanes provisioned under {home}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
