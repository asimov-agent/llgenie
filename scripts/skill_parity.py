#!/usr/bin/env python3
"""Report live↔tree skill parity for the host-agent profiles (issue #1924, Layer A).

The host agents keep their behaviour under `~/.hermes/profiles/<profile>/` OUTSIDE version control,
and the repo mirrors it under `agents/<profile>/`. Nothing checked that the two copies agree — the
planner's live `llgenie-bot-orchestration/skills/.../references/` held 249 files while the tree
carried 104 (145 live-only references at the issue's measurement), including the reference that
documents the auto-merge mechanism. A reference that exists only in the live profile is invisible to
review; this gate makes it visible.

Gate A is HOST-ONLY and READ-ONLY (a CI runner has no live profiles to compare, and the gate must
never write — `sync-agent-profile`'s write mode truncates silently when live > tree, which is
exactly the measured state):

  python3 scripts/skill_parity.py report    exit 0, print live-only / tree-only counts + names
  python3 scripts/skill_parity.py check     exit 1 when any profile has live-only or tree-only drift

The surface compared is the tree's OWN skill directories (`_tree_skill_dirs`): a live profile's
`skills/` also holds Hermes's bundled skill library (`.archive/`, `.bundled_manifest`, `.hub/`, the
shared `software-development/`, `research/`, the whole installed catalog), which is never mirrored in
the tree and is not the lane's behaviour. Bounding the live scan to the tree-mirrored skill dirs
keeps the report answerable — the planner's `llgenie-bot-orchestration/references/` then shows the
issue's 145 live-only references, not the thousands of bundled-library files. A live-only skill
DIRECTORY under the surface is named as a whole directory (issue #1086's absent-from-tree), not as
every file inside it.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / "agents"


def profiles(root: Path = REPO) -> list[str]:
    """The llgenie profiles the tree mirrors, in manifest order (a skill dir each)."""
    manifest = json.loads((root / "agents" / "manifest.json").read_text())
    return [p["name"] for p in manifest["profiles"]]


def _rel_files(base: Path) -> set[str]:
    """Every file under `base` as a relative path."""
    return {str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}


def tree_skill_dirs(root: Path, profile: str) -> list[Path]:
    """The tree's SKILL root dirs for a profile — the surface the tree mirrors.

    Each IMMEDIATE dir under `skills/` is a skill (or the first level of a nested skill); diffing
    its full subtree ONCE is what mirrors the live `skills/<skill>/**`. The surface is the tree's
    own dir set (never a nested subdir walked again inside its parent), so `github-issue-triage/`
    and `llgenie-bot-orchestration/` are each compared whole, and a live-only reference reports once
    as `<skill>/references/...`.
    """
    base = root / "agents" / profile / "skills"
    return [base] + sorted(p for p in base.iterdir() if p.is_dir())


def live_skills_root(root: Path = REPO) -> Path | None:
    """The profiles home, or None when this checkout is not on a machine with live profiles.

    `$HERMES_PROFILES_HOME` is the directory holding every profile; `$HERMES_PROFILE_HOME` is ONE
    profile's home, so its parent is used (the same reading `check_agent_profiles.live_root_info`
    uses).
    """
    plural = os.environ.get("HERMES_PROFILES_HOME")
    singular = os.environ.get("HERMES_PROFILE_HOME")
    if plural:
        return Path(plural).expanduser()
    if singular:
        return Path(singular).expanduser().parent
    return Path.home() / ".hermes" / "profiles"


def _bookkeeping(name: str) -> bool:
    """Hermes's own bookkeeping, never lane behaviour: hidden entries (`_bookkeeping` in
    check_agent_profiles), bytecode caches, the curator/hub records (`_bookkeeping` in #1069, #1086).
    A live-only directory that is one of these (`.archive/`, `.hub/`, `.curator_*`, `__pycache__/`)
    is the machine's, not the lane's."""
    return name == "__pycache__" or name.startswith(".")


def installed_library_names(skills_root: Path) -> set[str]:
    """The skill names Hermes's own install records name (`.bundled_manifest` + `.hub/lock.json`).

    Mirrors `check_agent_profiles.installed_library_names`: a skill the bundle ships or the hub
    fetched is the library, never this lane's behaviour (issue #1086). The shared library the
    profiles are seeded from (`<hermes-home>/skills`, the sibling of `profiles/`) is excluded by not
    being under the live profile's `skills/`-mirrored surface at all.
    """
    names: set[str] = set()
    manifest = skills_root / ".bundled_manifest"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.split(":", 1)[0].strip()
            if name:
                names.add(name)
    lock = skills_root / ".hub" / "lock.json"
    if lock.is_file():
        try:
            data = json.loads(lock.read_text(encoding="utf-8", errors="replace"))
            installed = data.get("installed") if isinstance(data, dict) else None
            if isinstance(installed, dict):
                names.update(n for n in installed if isinstance(n, str))
        except (OSError, json.JSONDecodeError):
            pass
    return names


def shared_library_names(homes: Path) -> set[str]:
    """SKILL NAMES the shared library (<hermes-home>/skills, the SIBLING of the profiles dir) carries.

    Hermes seeds every profile from `<hermes-home>/skills` plus the bundle/hub records. A skill (or
    category) present in that shared library is the machine's library, never a lane's — it shows up
    as a "live-only directory" for every profile for no reason (issue #1086 names the same source).
    """
    lib = homes.parent / "skills"
    if not lib.is_dir():
        return set()
    names = {p.name for p in lib.iterdir() if p.is_dir()}
    for p in lib.rglob("*"):
        if p.is_dir():
            names.add(p.name)
    return names


def profile_drift(root: Path = REPO):
    """Per-profile (live-only, tree-only) file sets, bounded to the tree-mirrored skill dirs."""
    homes = live_skills_root(root)
    if not homes or not homes.is_dir():
        return None
    report = {}
    for name in profiles(root):
        surface = tree_skill_dirs(root, name)
        live_skills = homes / name / "skills"
        if not surface or not live_skills.is_dir():
            continue
        tree_only_dirs: list[str] = []
        live_only_dirs: list[str] = []
        live_files: set[str] = set()
        tree_files: set[str] = set()
        for tdir in surface:
            rel = str(tdir.relative_to(root / "agents" / name / "skills"))
            if rel in ("", "."):
                continue  # the skills ROOT hosts the bundled library too; mirror only real skill dirs
            live_dir = live_skills / rel
            if not live_dir.is_dir():
                continue  # tree-carried dir missing in live: files count as tree-only below
            live_files |= _rel_files(live_dir)
            tree_files |= _rel_files(tdir)
        # live-only skill DIRECTORY under the surface that is NOT the lane: hidden bookkeeping
        # (`.archive/`, `.hub/`, `.curator_*`) and the library the bundle/hub records name are the
        # machine's, never lane behaviour (mirrors check_agent_profiles #1086).
        library = installed_library_names(live_skills) | shared_library_names(homes)
        live_names = {p.name for p in live_skills.iterdir() if p.is_dir()}
        tree_names = {p.name for p in (root / "agents" / name / "skills").iterdir() if p.is_dir()}
        live_only_dirs = sorted(n for n in (live_names - tree_names)
                                if not _bookkeeping(n) and n not in library)
        tree_only_dirs = sorted(n for n in (tree_names - live_names)
                                if not _bookkeeping(n) and n not in library)
        report[name] = {
            "live_only_files": sorted(live_files - tree_files),
            "tree_only_files": sorted(tree_files - live_files),
            "live_only_dirs": live_only_dirs,
            "tree_only_dirs": tree_only_dirs,
        }
    return report


def findings(drift: dict) -> list[str]:
    """One finding per profile with any drift under the tree-mirrored surface."""
    out = []
    for name, d in drift.items():
        if d["live_only_dirs"]:
            out.append(f"{name}: live-only skill director(y/ies) never mirrored in the tree: "
                       f"{', '.join(d['live_only_dirs'])}")
        if d["tree_only_dirs"]:
            out.append(f"{name}: tree-only skill director(y/ies) absent from the live profile: "
                       f"{', '.join(d['tree_only_dirs'])}")
        lof = d["live_only_files"]
        if lof:
            shown = ", ".join(lof[:30])
            out.append(f"{name}: {len(lof)} live-only skill file(s) under the mirrored skills: "
                       f"{shown}{' …' if len(lof) > 30 else ''}")
        tof = d["tree_only_files"]
        if tof:
            shown = ", ".join(tof[:20])
            out.append(f"{name}: {len(tof)} tree-only skill file(s): {shown}"
                       f"{' …' if len(tof) > 20 else ''}")
    return out


def report(root: Path = REPO) -> int:
    homes = live_skills_root(root)
    if not homes or not homes.is_dir():
        print(f"[skill-parity] no live profiles at `{homes}` — host-only gate, nothing to compare "
              f"here (exit 0, no verdict)")
        return 0
    drift = profile_drift(root)
    rows = findings(drift) if drift else []
    print(f"[skill-parity] comparing agents/<profile>/skills/ against live profiles at `{homes}` "
          f"(read-only, tree-mirrored skills only) ")
    if not rows:
        print("[skill-parity] OK: every llgenie profile's mirrored live skills match the tree")
        return 0
    for row in rows:
        print(f"  - {row}")
    return 1


def check(root: Path = REPO) -> int:
    return report(root) if profile_drift(root) is not None else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report live↔tree skill parity for host-agent profiles "
                                             "(issue #1924)")
    ap.add_argument("cmd", choices=("report", "check"))
    ap.add_argument("--root", default=str(REPO))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    return report(root) if args.cmd == "report" else check(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
