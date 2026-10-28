#!/usr/bin/env python3
"""Make a host agent's profile the repository's copy of itself (issue #791).

The two host agents keep their behaviour in `~/.hermes/profiles/<profile>/` (`SOUL.md` plus
`skills/`), outside version control. That behaviour lives in this tree now —
`agents/<profile>/…` — so this script is the one seam between the two: it copies the tree INTO the
profile's Hermes home, and `--check` reads every file back and names the first one that differs.

The shape is the write-then-verify one `scripts/hermes_skills_register.py` already uses for
`skills.external_dirs`: a copy that is not read back cannot be trusted, and a profile that silently
kept an older `SOUL.md` is exactly the drift the issue exists to end.

What it never does: it writes only the files the tree carries, so the profile's own skills, memory,
`state.db`, sessions and `.env` are untouched — and there is no delete path at all, because a sync
that removed a skill from a live profile would be a behaviour change nobody reviewed.

Destination: `--dest`, else `$HERMES_PROFILE_HOME` (the PROFILE's home, not a profiles/ directory),
else `~/.hermes/profiles/<profile>/`.

Exit codes: 0 ok, 1 a file differs after the write or under `--check`, 2 unknown profile / missing
tree / unreadable destination — never a silent pass.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_agent_profiles import AGENTS_DIR, MANIFEST, profiles_from_manifest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def profile_files(agents: Path, name: str) -> list[Path]:
    """Every file the tree carries for *name*, in a stable order."""
    base = agents / name
    return sorted(p for p in base.rglob("*") if p.is_file())


def destination(profile: str, explicit: str | None) -> tuple[Path, str]:
    """The profile's Hermes home, and the knob that chose it (printed, so a run says which it used)."""
    if explicit:
        return Path(explicit).expanduser(), "--dest"
    env = os.environ.get("HERMES_PROFILE_HOME")
    if env:
        return Path(env).expanduser(), "$HERMES_PROFILE_HOME"
    return Path.home() / ".hermes" / "profiles" / profile, "default (~/.hermes/profiles/<profile>)"


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def check(agents: Path, name: str, dest: Path) -> int:
    """Compare every file the tree carries against the profile; name the first that differs."""
    files = profile_files(agents, name)
    if not files:
        print(f"[agent-profile] FAIL: {agents.name}/{name} carries no file, so there is nothing to "
              f"sync for {name}", file=sys.stderr)
        return 2
    differing: list[str] = []
    for path in files:
        rel = _rel(path, agents / name)
        target = dest / rel
        if not target.is_file():
            differing.append(f"{rel} (missing in the profile)")
        elif not filecmp.cmp(path, target, shallow=False):
            differing.append(f"{rel} (differs: tree {path.stat().st_size} b, profile "
                             f"{target.stat().st_size} b)")
    if differing:
        for line in differing:
            rel = line.split(" (")[0]
            print(f"[agent-profile] DIFFERS {agents.name}/{name}/{rel}: {line}", file=sys.stderr)
        print(f"[agent-profile] {len(differing)} of {len(files)} file(s) differ from {dest} — "
              f"first: {differing[0].split(' (')[0]}. Run `make sync-agent-profile PROFILE={name}` "
              "to make the profile the repository's copy", file=sys.stderr)
        return 1
    print(f"[agent-profile] OK: {len(files)} file(s) of {agents.name}/{name} match {dest} "
          f"byte for byte")
    return 0


#: A synced file smaller than this fraction of the live one is treated as a truncated seed, not an edit.
#: The defect this exists for: a seed taken from an issue's excerpt stopped at an inner code fence, so
#: `sync` would have replaced a 7,509-byte rulebook with 5,149 bytes of it, with every gate green.
SHRINK_FLOOR = 0.75


def shrinks(agents: Path, name: str, dest: Path) -> list[tuple[str, int, int]]:
    """Every (relative path, tree size, live size) this sync would shrink past `SHRINK_FLOOR`."""
    out: list[tuple[str, int, int]] = []
    for path in profile_files(agents, name):
        rel = _rel(path, agents / name)
        target = dest / rel
        if not target.exists():
            continue
        tree, live = path.stat().st_size, target.stat().st_size
        if live and tree < live * SHRINK_FLOOR:
            out.append((rel, tree, live))
    return out


def write(agents: Path, name: str, dest: Path, force: bool = False) -> int:
    """Copy each file in, then read every one back; a read-back mismatch is a failure."""
    files = profile_files(agents, name)
    if not files:
        print(f"[agent-profile] FAIL: {agents.name}/{name} carries no file, so there is nothing to "
              f"sync for {name}", file=sys.stderr)
        return 2
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[agent-profile] FAIL: cannot create {dest}: {exc}", file=sys.stderr)
        return 2
    shrinking = shrinks(agents, name, dest)
    if shrinking and not force:
        for rel, tree, live in shrinking:
            print(f"[agent-profile] REFUSED {agents.name}/{name}/{rel}: the tree has {tree} b, the live "
                  f"profile has {live} b — a sync would replace {live} bytes of rulebook with {tree}. "
                  f"That is a truncated seed, not an edit; fix the seed, or pass --force to mean it.",
                  file=sys.stderr)
        return 3
    written: list[str] = []
    for path in files:
        rel = _rel(path, agents / name)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        written.append(rel)
    mismatched = [rel for rel in written
                  if not filecmp.cmp(agents / name / rel, dest / rel, shallow=False)]
    if mismatched:
        print(f"[agent-profile] FAIL: wrote {len(written)} file(s) into {dest} but "
              f"{len(mismatched)} did not read back identical — first: {mismatched[0]}",
              file=sys.stderr)
        return 1
    print(f"[agent-profile] {agents.name}/{name} -> {dest} ({len(written)} file(s))")
    print(f"[agent-profile] verified: {len(written)} file(s) read back identical")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--profile", required=True, help="the profile name, as the manifest lists it")
    parser.add_argument("--check", action="store_true",
                        help="compare instead of writing; exit 1 naming the first differing path")
    parser.add_argument("--dest", default=None,
                        help="the profile's Hermes home (default: $HERMES_PROFILE_HOME, else "
                             "~/.hermes/profiles/<profile>)")
    parser.add_argument("--root", default=str(REPO_ROOT), help="tree to read (the tests use this)")
    parser.add_argument("--force", action="store_true",
                        help="allow a tree file that is smaller than the live one (a deliberate "
                             "shortening); without it a truncated seed is refused")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    agents = (root / AGENTS_DIR) if not AGENTS_DIR.is_absolute() else AGENTS_DIR
    if not agents.is_dir():
        print(f"[agent-profile] FAIL: {agents} is not a directory — the host agents' tree is "
              "missing, so there is nothing to sync from", file=sys.stderr)
        return 2
    listed = [profile["name"] for profile in profiles_from_manifest(agents)]
    if args.profile not in listed:
        print(f"[agent-profile] FAIL: {args.profile!r} is not in {agents.name}/{MANIFEST} "
              f"(listed: {', '.join(listed) or '(none)'}) — an unknown profile is an error, never "
              "a no-op pass", file=sys.stderr)
        return 2
    if not (agents / args.profile).is_dir():
        print(f"[agent-profile] FAIL: {agents.name}/{args.profile} does not exist, though the "
              f"manifest lists it", file=sys.stderr)
        return 2

    dest, source = destination(args.profile, args.dest)
    print(f"[agent-profile] {args.profile}: destination {dest} (from {source})")
    if args.check:
        return check(agents, args.profile, dest)
    return write(agents, args.profile, dest, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
