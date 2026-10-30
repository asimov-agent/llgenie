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

The sync is ONE-WAY: the tree is the source, the live profile is a copy, and a live-only edit is a
*finding* in `check_agent_profiles.py` (which profile, by how many bytes, and the remedy), never
silent drift that the tree re-takes (issue #968).

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

from check_agent_profiles import (  # noqa: E402
    AGENTS_DIR, MANIFEST, _stamp, profiles_from_manifest, source_time,
)

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
    truncated: list[tuple[str, int, int]] = []
    for path in files:
        rel = _rel(path, agents / name)
        target = dest / rel
        if not target.is_file():
            differing.append(f"{rel} (missing in the profile)")
        elif not filecmp.cmp(path, target, shallow=False):
            tree_size, live_size = path.stat().st_size, target.stat().st_size
            differing.append(f"{rel} (differs: tree {tree_size} b, profile {live_size} b)")
            if live_size > tree_size:
                truncated.append((rel, tree_size, live_size))
    if differing:
        for line in differing:
            rel = line.split(" (")[0]
            print(f"[agent-profile] DIFFERS {agents.name}/{name}/{rel}: {line}", file=sys.stderr)
        # A differing file whose LIVE copy is longer is the dangerous direction: syncing it would delete
        # live behaviour, so `--check` must say that rather than the neutral "differs" (issue #791).
        for rel, tree_size, live_size in truncated:
            print(f"[agent-profile] TRUNCATED? {agents.name}/{name}/{rel}: the tree copy is {tree_size} b "
                  f"and the profile's is {live_size} b — syncing would REPLACE {live_size - tree_size} b of "
                  f"live behaviour. Sync is one-way (tree → live), so fix the TREE: a live-only edit "
                  f"is a finding in check_agent_profiles.py — commit it via an issue+PR under "
                  f"agents/{name}/, then re-sync.", file=sys.stderr)
        print(f"[agent-profile] {len(differing)} of {len(files)} file(s) differ from {dest} — "
              f"first: {differing[0].split(' (')[0]}. "
              + (f"{len(truncated)} of them would SHRINK the live profile, so the tree copy is the "
                 "truncated one: do not sync it until it is re-copied. "
                 if truncated else "")
              + f"Run `make sync-agent-profile PROFILE={name}` "
              "to make the profile the repository's copy", file=sys.stderr)
        return 1
    print(f"[agent-profile] OK: {len(files)} file(s) of {agents.name}/{name} match {dest} "
          f"byte for byte")
    return 0


#: A synced file smaller than this fraction of the live one is treated as a truncated seed, not an edit.
#: The defect this exists for: a seed taken from an issue's excerpt stopped at an inner code fence, so
#: `sync` would have replaced a 7,509-byte rulebook with 5,149 bytes of it, with every gate green.
SHRINK_FLOOR = 0.75


def _rule_lines(text: str) -> list[str]:
    """The non-blank lines, which is what a rulebook is made of — prose indentation is not the content."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def shrinks(agents: Path, name: str, dest: Path) -> list[tuple[str, int, int, int]]:
    """Every file this sync would shrink: (relative path, tree bytes, live bytes, lines the live one loses).

    Two signals, and the **content** one decides, because a size ratio alone cannot tell a truncated
    seed from a reformatted file (rule from issue #791's review): if every non-blank line the tree has
    also appears in the live file, and the live file has lines the tree does not, then the tree is a
    SUBSET — a prefix, not a rewrite — and syncing it deletes rules while reporting success.
    """
    out: list[tuple[str, int, int, int]] = []
    for path in profile_files(agents, name):
        rel = _rel(path, agents / name)
        target = dest / rel
        if not target.exists():
            continue
        tree_text, live_text = path.read_text(), target.read_text()
        tree, live = path.stat().st_size, target.stat().st_size
        tree_lines, live_lines = _rule_lines(tree_text), _rule_lines(live_text)
        subset = (tree_lines != live_lines and set(tree_lines) <= set(live_lines))
        lost = len([ln for ln in live_lines if ln not in set(tree_lines)])
        # Two signals, and BOTH now require a lost line, because that is the only harm: a tree that is
        # smaller only because the live file REPEATS a block loses nothing (measured: 16,694 b against
        # 10,824 b, "would delete 0 line(s)"), and a deliberate rewrite keeps being allowed as long as it
        # is neither a prefix of live nor far below the size floor.
        if lost and (subset or (live and tree < live * SHRINK_FLOOR)):
            out.append((rel, tree, live, lost))
    return out


def _loses_live_lines(tree_text: str, live_text: str) -> bool:
    """Would writing the tree drop a line the live file has? That, not the mtime, is the harm."""
    return bool(set(_rule_lines(live_text)) - set(_rule_lines(tree_text)))


def newer_than_source(agents: Path, name: str, dest: Path) -> list[tuple[str, float, float]]:
    """Live files edited AFTER the tree copy was committed: (relative path, source time, live mtime).

    The defect this exists for: the live profile is a MOVING reference — another lane edits it while a PR
    is under review — so `sync` into such a file is a silent merge in the wrong direction, on the write
    path, where no read-time caveat can see it. Measured tonight, a `cp` from live was one command away
    from deleting twelve lines of tree-only content that existed nowhere else (issue #924).
    """
    out: list[tuple[str, float, float]] = []
    for path in profile_files(agents, name):
        rel = _rel(path, agents / name)
        target = dest / rel
        if not target.exists():
            continue
        src, live = source_time(agents, name, path), target.stat().st_mtime
        if live <= src + 1:  # a second of slack: filesystems store whole seconds, git stores integers
            continue
        # The mtime is a proxy for "someone else wrote this"; the HARM is losing a line they wrote. Two
        # cases where the write destroys nothing and the refusal would be a false positive:
        #   - the bytes are already identical, so the sync writes nothing at all;
        #   - every live line also exists in the tree, so the write cannot drop one.
        if filecmp.cmp(path, target, shallow=False) or not _loses_live_lines(
                path.read_text(), target.read_text()):
            continue
        out.append((rel, src, live))
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
    # A live file edited after our commit is the more dangerous case, so it is refused FIRST: the shrink
    # message would describe a content problem when the real problem is that another lane is editing.
    moving = newer_than_source(agents, name, dest)
    if moving and not force:
        for rel, src, live in moving:
            target = dest / rel
            tree_bytes, live_bytes = (agents / name / rel).stat().st_size, target.stat().st_size
            lost = [ln for ln in _rule_lines(target.read_text())
                    if ln not in set(_rule_lines((agents / name / rel).read_text()))]
            # Order the message by what was actually checked: first the mtime fact, then — only when the
            # content differs — the line count. The tree has no ownership information, so never say whose
            # work it is; "another lane's work" was a guess the harness had no right to make.
            print(f"[agent-profile] REFUSED {agents.name}/{name}/{rel}: the live file was edited AFTER "
                  f"the tree copy was committed — live {_stamp(live)}, source commit {_stamp(src)} — so a "
                  f"sync would overwrite {live_bytes:,} b with {tree_bytes:,} b"
                  + (f", and the content differs: {len(lost)} live line(s) the tree lacks" if lost else "")
                  + ". Read the live file and merge deliberately, or pass --force to mean it.",
                  file=sys.stderr)
        return 4
    shrinking = shrinks(agents, name, dest)
    if shrinking and not force:
        for rel, tree, live, lost in shrinking:
            how = ("is SMALLER and its lines are a subset of the live file's"
                   if tree < live else "keeps every line it has inside the live file's, but drops live ones")
            print(f"[agent-profile] REFUSED {agents.name}/{name}/{rel}: the tree file {how} — "
                  f"{tree} b against {live} b — so a sync would delete {lost} line(s) of rulebook. "
                  f"That is a truncated seed, not an edit; fix the seed, or pass --force to mean it.",
                  file=sys.stderr)
        return 3
    written: list[str] = []
    # Captured BEFORE the copy: after it every file exists and matches, so asking then answers "no change"
    # for every run — an instrument reporting a property it did not check.
    existed = {rel for rel in (_rel(p, agents / name) for p in files) if (dest / rel).exists()}
    differed = {rel for rel in existed
                if not filecmp.cmp(agents / name / rel, dest / rel, shallow=False)}
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
    # Never say "identical" for a file whose content changed: that claim is about what was WRITTEN, not
    # about what was THERE, and the difference is what shipped a 2,360-byte deletion (issue #791 review).
    # A --force run is the ONE case where a file legitimately shrinks, which is exactly when the log
    # must say so: "verified … identical" over a 2,360-byte deletion is the defect this guard exists for,
    # and it survives --force unless the message names the shrink and both sizes.
    shrunk_note = ""
    if shrinking:
        rel, tree, live, lost = shrinking[0]
        shrunk_note = (f", {len(shrinking)} shrank by --force ({live:,} b → {tree:,} b"
                       + (f", {lost} line(s) removed" if lost else "") + ")")
    moving_note = ""
    if moving:
        rel, src, live = moving[0]
        moving_note = (f", {len(moving)} overwrote a live file NEWER than the source commit by --force "
                       f"(live {_stamp(live)} vs source {_stamp(src)})")
    print(f"[agent-profile] verified: {len(written)} copied and read back as written"
          + (f", {len(existed)} replaced an existing file" if existed else "")
          + (f", {len(differed)} of them had different content" if differed else "")
          + shrunk_note + moving_note)
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
