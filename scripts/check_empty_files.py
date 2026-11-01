#!/usr/bin/env python3
"""The zero-byte file gate (issue #1509): refuse empty files being checked in.

`.wt-probe.txt` — a 0-byte blob, blob `e69de29b` — rode a squash (#1467) to `main`
because no gate rejected it: the linefeed/editorconfig and docs gates never look at
path size, so a stray empty diagnostic can land silently. A `.gitkeep` is the *only*
legitimate empty-tracked-file case, so the gate is deliberately generous to sentinel
names and refuses everything else that is zero bytes.

What the gate refuses is the shape that let the probe slip in: a path *added* by the
change set (`--diff-filter=A`) that is zero bytes. Concretely:

- **added** (the default gate, `--base`): every path that was *added* between the
  merge base of a ref and HEAD (three-dot `base...HEAD`) and is zero bytes on disk.
  CI passes `--base origin/main` on a PR push — or the merged-into ref on a main
  push — so a change that introduces an empty path fails, naming it.
- **present** (`--all`): additionally every currently-tracked zero-byte non-sentinel
  file, regardless of which change added it — the "current main has no zero-byte
  files" invariant from the issue's acceptance. This is OPT-IN because a PR whose
  base still carries a pre-existing empty file (the `.wt-probe.txt` pending #1508's
  removal) would red on `--all` while its own diff is clean; the added-paths gate is
  the branch's responsibility, `--all` is the tree's.

A path is allow-listed when its basename is a `.gitkeep`-style sentinel (a dot-file
named `.gitkeep` / `.keep`, or a `.keepXYZ` marker) — the one case where emptiness
is the point — or when its exact relative path is passed via `--allow`.

Usage:
    python3 scripts/check_empty_files.py check --base origin/main   # gate on added paths
    python3 scripts/check_empty_files.py check --all                # also present empties
    python3 scripts/check_empty_files.py report                     # the findings, or OK
    python3 scripts/check_empty_files.py report --all
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The only legitimate empty-tracked-file names — a directory placeholder whose whole
#: point is that the directory is kept but empty. Everything else zero bytes is refused.
_SENTINEL_NAMES = (".gitkeep", ".keep")
_SENTINEL_RE = re.compile(r"^(?:\.gitkeep|\.keep)(?:$|[._-])")


def _is_sentinel(path: str) -> bool:
    """True when a path is an allow-listed directory sentinel (.gitkeep-style)."""
    return bool(_SENTINEL_RE.match(path.rsplit("/", 1)[-1])) or path in _SENTINEL_NAMES


def _allowlisted(path: str, allow: tuple[str, ...]) -> bool:
    return path in allow or any(path == a or path.startswith(a.rstrip("/") + "/") for a in allow)


def _added_paths(root: Path, base: str) -> list[str]:
    """Paths *added* between the merge base of `base` and HEAD (three-dot)."""
    r = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=A",
         f"{base}...HEAD"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"cannot diff against {base}")
    return [p for p in r.stdout.splitlines() if p.strip()]


def _tracked_paths(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode().strip() or "cannot list tracked files")
    return [p for p in r.stdout.decode().split("\0") if p]


def _empty(rel: str, root: Path) -> bool:
    p = root / rel
    try:
        return p.is_file() and p.stat().st_size == 0
    except OSError:
        return False


def _exempt(rel: str, allow: tuple[str, ...]) -> bool:
    return _allowlisted(rel, allow) or _is_sentinel(rel)


def findings(root: Path = REPO, base: str = "", allow: tuple[str, ...] = (),
             all_tracked: bool = False) -> list[dict]:
    items: list[dict] = []
    empty_added: dict[str, dict] = {}

    if base:
        for rel in _added_paths(root, base):
            if _exempt(rel, allow):
                continue
            if _empty(rel, root):
                empty_added[rel] = {
                    "key": "added",
                    "where": rel,
                    "detail": f"`{rel}` is ADDED EMPTY — an added file must carry a byte "
                              f"(issue #1509)",
                }

    if all_tracked:
        for rel in _tracked_paths(root):
            if rel in empty_added or _exempt(rel, allow):
                continue
            if _empty(rel, root):
                empty_added[rel] = {
                    "key": "present",
                    "where": rel,
                    "detail": f"`{rel}` is an empty file present in the tree — commit "
                              f"nothing of zero bytes (issue #1509)",
                }

    return list(empty_added.values())


def render(items: list[dict]) -> str:
    if not items:
        return "[check-empty-files] OK: no zero-byte non-sentinel file (added or present)"
    lines = [f"[check-empty-files] {len(items)} empty-file path(s):"]
    lines += [f"  {it['where']}: {it['detail']}" for it in items]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_empty_files.py", description=__doc__)
    p.add_argument("cmd", choices=("check", "report"))
    p.add_argument("--root", default=str(REPO))
    p.add_argument("--base", default="",
                   help="base ref whose additions are the gate (three-dot diff; e.g. "
                        "origin/main on a PR, or the merged-into ref on a main push)")
    p.add_argument("--all", dest="all_tracked", action="store_true",
                   help="also refuse every currently-present empty tracked file, not just "
                        "paths added by this change set")
    p.add_argument("--allow", nargs="*", default=[],
                   help="exact paths (or prefixes) always exempt from the zero-byte rule")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not args.base and not args.all_tracked:
        # Nothing to reject — a check with neither base refs nor --all is a no-op gate,
        # which would silently "pass". Make it a misuse error rather than a false green.
        print("[check-empty-files] nothing to gate: pass --base <ref> (added-paths) "
              "or --all (present empties)",
              file=sys.stderr)
        return 2
    items = findings(root, args.base, tuple(args.allow), args.all_tracked)
    if args.cmd == "report":
        print(render(items))
        return 0
    print(render(items), file=sys.stdout if not items else sys.stderr)
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
