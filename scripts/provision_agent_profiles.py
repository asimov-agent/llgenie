#!/usr/bin/env python3
"""materialise every lane's behaviour from agents/<profile>/ into its Hermes home (issue #2165).

The issue: `agents/<profile>/` versions every lane's `SOUL.md` and `skills/`, and
`make sync-agent-profile PROFILE=<p>` is the one seam that copies it — but nothing
invokes that seam at profile-creation/rebuild time, so a rebuilt profile starts
with whatever its home happens to contain and fails silently (a missing or older
`SOUL.md` produces no error and no log line). Measured 2026-11-08: every hit of
`sync-agent-profile|agent_profile_sync` across workflows/scripts/Makefile is a
declaration, hint, promise or report — there is no caller. That is why #2090
measured 586 live->tree drift findings over 474 files across 13 lanes.

This script is that caller. It materialises EVERY profile the manifest lists,
idempotently, and it reuses `agent_profile_sync`'s own `write`/`check` — never
reimplementing the copy — so the write-then-read-back discipline and the
deliberate no-delete path are preserved by construction.

USAGE
  provision_agent_profiles.py [--dest BASE] [--check] [--root ROOT]

  BASE is the PARENT of the per-profile homes (a "profiles" directory), because
  `agent_profile_sync` takes a *profile home* per profile. Default: the parent of
  `$HERMES_PROFILE_HOME` (the per-profile home), else `~/.hermes/profiles`.

  Without --check: write every profile (idempotent; a second run is a no-op).
  With    --check: compare every profile back against the tree and exit non-zero
                   naming the profile and the first differing path.

Exit: 0 all profiles ok; 1 a profile differs (--check) or a write read-back failed;
2 an unknown/incomplete profile or a missing tree or destination (never a silent pass).

Safety (inherited from `agent_profile_sync`): copy is ONE-WAY (tree is source);
we write only files the tree carries, so a profile's memory, `state.db`, sessions
and `.env` are untouched; there is NO delete path; a live-only edit stays a
*finding* reported by the comparison, never something provisioning re-takes.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_profile_sync import AGENTS_DIR, REPO_ROOT, check, write  # noqa: E402
from check_agent_profiles import MANIFEST, profiles_from_manifest  # noqa: E402

DEFAULT_BASE = Path.home() / ".hermes" / "profiles"


def _base(explicit: str | None) -> Path:
    """Resolve the profiles/ (parent) directory. Precedence: --dest, else the
    parent of $HERMES_PROFILE_HOME (which the per-profile seam already honours),
    else ~/.hermes/profiles."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    singular = os.environ.get("HERMES_PROFILE_HOME")
    if singular:
        return Path(singular).expanduser().resolve().parent
    return DEFAULT_BASE


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="materialise every lane's agents/<profile>/ into its "
                                             "Hermes home (issue #2165)")
    ap.add_argument("--dest", default=None,
                    help="the PARENT profiles/ directory (default: parent of $HERMES_PROFILE_HOME, "
                         "else ~/.hermes/profiles)")
    ap.add_argument("--check", action="store_true",
                    help="compare every profile back against the tree; exit non-zero naming the "
                         "profile and path on any difference")
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree to read (tests use this)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    agents = (root / AGENTS_DIR) if not AGENTS_DIR.is_absolute() else AGENTS_DIR
    if not agents.is_dir():
        print(f"[provision] FAIL: {agents} is not a directory — nothing to provision from",
              file=sys.stderr)
        return 2
    profiles = [p["name"] for p in profiles_from_manifest(agents)]
    if not profiles:
        print(f"[provision] FAIL: {agents.name}/{MANIFEST} lists no profiles", file=sys.stderr)
        return 2

    base = _base(args.dest)
    base.mkdir(parents=True, exist_ok=True)

    failures: list[tuple[str, Path, int]] = []
    for name in profiles:
        home = base / name
        rc = check(agents, name, home) if args.check else write(agents, name, home)
        if rc != 0:
            failures.append((name, home, rc))

    if failures:
        for name, home, rc in failures:
            print(f"[provision] FAIL {name}: {'differs from' if args.check else 'did not land at'} "
                  f"{agents.name}/{name} at {home} (rc={rc})", file=sys.stderr)
        print(f"[provision] {'gate' if args.check else 'provision'}: {len(failures)} of "
              f"{len(profiles)} profile(s) {'diverge from' if args.check else 'failed to write from'} "
              f"the tree", file=sys.stderr)
        return 1

    # after a write, the gate proves what was materialised matches the tree (a write
    # that read back cleanly satisfies the AC's "fresh empty home matches exactly").
    if not args.check:
        rc_final = _gate(agents, profiles, base)
        if rc_final != 0:
            return rc_final

    print(f"[provision] OK: {len(profiles)} profile(s) {'match' if args.check else 'materialised'} "
          f"from {agents.name}/ into {base}")
    return 0


def _gate(agents: Path, profiles: list[str], base: Path) -> int:
    bad: list[str] = []
    for name in profiles:
        if check(agents, name, base / name) != 0:
            bad.append(name)
    if bad:
        print(f"[provision] verify: {len(bad)} profile(s) did not match after write: {', '.join(bad)}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
