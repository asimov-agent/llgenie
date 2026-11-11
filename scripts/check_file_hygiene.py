#!/usr/bin/env python3
"""The stray run-artifact gate (issue #2484): refuse committed `*.log` and dot-scratch files.

`.unit2.log` (10 bytes) and `.pr874.md` (3,221 bytes) rode two PRs (#2277, #1738) to `main`
because no gate rejected a committed runtime artifact: `.gitignore` listed only a handful of
log names, so any `*.log` the tools started writing was committable, and a dot-prefixed
`.pr874.md` named after the run that produced it looked like docs. A `*.log` that lands once
stays in history and re-appears in every worktree and PR diff, adding review noise and
secret-exposure surface (logs can carry tokens, paths, transcripts).

The gate scans every file git **tracks** (the PR tree) and refuses two runtime-artifact shapes:

- any path ending in `.log` (categorical — a blanket `*.log`, not a blacklist of known names);
- a dot-prefixed hidden scratch name `.<word><digits>.<ext>` (e.g. `.pr874.md`, `.unit2.log`) —
  a leading dot, then letters/digits with at least one digit before the extension dot.

An exception is allowlist-driven and dated, exactly like the docs and skill-size exceptions
(`tests/fixtures/file-hygiene-exceptions.json`): an intentional file that legitimately matches
(e.g. a fixture log under `tests/fixtures/`) is recorded there with a reason, a date and the
issue that decided it. An exception whose file is no longer tracked, or no longer matches any
pattern, is STALE and fails — an exemption cannot outlive its reason.

The gate lists findings as paths only (with a short reason label), never file contents,
consistent with the log-scrutiny rules.

Usage:
    python3 scripts/check_file_hygiene.py check    # gate: fail on any artifact or stale exception
    python3 scripts/check_file_hygiene.py report   # print the findings, or OK
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_EXCEPTIONS = "tests/fixtures/file-hygiene-exceptions.json"

#: Every path ending in `.log` — the blanket rule (case-insensitive: `foo.LOG` is a log too).
LOG_RE = re.compile(r"\.log$", re.I)
#: A dot-prefixed hidden scratch name `.<word><digits>.<ext>` — leading dot, letters/digits with
#: at least one digit immediately before the extension dot (e.g. `.pr874.md`, `.unit2.log`).
#: `.env.example` and `.gitignore` (no digit in the stem) never match, so a valued hidden file
#: is not caught by accident.
SCRATCH_RE = re.compile(r"(?:^|/)\.[A-Za-z0-9_]*[0-9]+\.[A-Za-z0-9]+$")

_PATTERNS = (
    ("log", LOG_RE, "a `*.log` runtime artifact — no log of any name may be committed"),
    ("scratch", SCRATCH_RE, "a dot-prefixed `<word><digits>.<ext>` run-artifact scratch name"),
)


def _tracked_paths(root: Path) -> list[str]:
    r = subprocess.run([  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        "git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode().strip() or "cannot list tracked files")
    return [p for p in r.stdout.decode().split("\0") if p]


def _matches(rel: str) -> str | None:
    """The name of the first artifact pattern `rel` matches, or ``None``."""
    for name, rx, _ in _PATTERNS:
        if rx.search(rel):
            return name
    return None


def _load_exceptions(path: Path) -> tuple[dict, list[dict]]:
    """`{path: entry}` from the exceptions fixture, plus any structural findings.

    Mirrors the docs/skill-size exception fixtures: an entry must be an object with a `reason`,
    a `date` and an `issue`, and every value must be non-empty — an omission is never a valid
    decision (issue #2484).
    """
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {}, [{"key": "bad-exceptions", "where": str(path),
                     "detail": f"{path}: not valid JSON: {e}"}]
    files = data.get("files") or {}
    if not isinstance(files, dict):
        return {}, [{"key": "bad-exceptions", "where": str(path),
                     "detail": f"{path}: 'files' must be an object"}]
    structural: list[dict] = []
    for rel, entry in files.items():
        if not isinstance(entry, dict):
            structural.append({"key": "bad-exceptions", "where": str(path),
                               "detail": f"{path}: {rel!r} must be an object"})
            continue
        for key in ("reason", "date", "issue"):
            if not entry.get(key):
                structural.append({"key": "bad-exceptions", "where": str(path),
                                   "detail": f"{path}: {rel!r} lacks {key!r}"})
    return files, structural


def findings(root: Path = REPO, exceptions: str = DEFAULT_EXCEPTIONS) -> list[dict]:
    """Every artifact and stale-exception finding, from the real tracked tree."""
    except_path = root / exceptions
    file_exceptions, structural = _load_exceptions(except_path)

    tracked = _tracked_paths(root)
    # `{path: pattern name}` for every tracked path that matches an artifact pattern.
    matched = {rel: name for rel in tracked if (name := _matches(rel))}

    out: list[dict] = []
    # A tracked artifact with no recorded exception refuses the tree (paths only).
    for rel in sorted(matched):
        if rel in file_exceptions:
            continue
        _, _, label = next(p for p in _PATTERNS if p[0] == matched[rel])
        out.append({"key": "artifact", "where": rel,
                    "detail": f"`{rel}` is {label} (issue #2484) — remove it, or record it in "
                              f"{exceptions} with a reason"})
    # A recorded exception whose file is no longer tracked or no longer matches is STALE.
    for rel in sorted(file_exceptions):
        if rel in matched:
            continue
        out.append({"key": "stale-exception", "where": rel,
                    "detail": f"{exceptions}: {rel!r} is STALE — it is not a tracked "
                              f"*.log/dot-scratch artifact any more; delete the entry"})
    return structural + out


def render(items: list[dict]) -> str:
    if not items:
        return ("[check-file-hygiene] OK: no tracked `*.log` or dot-prefixed scratch artifact, "
                "and no stale exception")
    paths = [i["where"] for i in items]
    lines = [f"[check-file-hygiene] {len(paths)} path(s):"]
    lines += [f"  {i['where']}: {i['detail']}" for i in items]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_file_hygiene.py", description=__doc__)
    p.add_argument("cmd", choices=("check", "report"))
    p.add_argument("--root", default=str(REPO),
                   help="checkout whose tracked files are scanned (a test seam)")
    p.add_argument("--exceptions", default=DEFAULT_EXCEPTIONS,
                   help="path, relative to --root, of the dated exception fixture (a test seam)")
    args = p.parse_args(argv)
    root = Path(args.root)
    items = findings(root, args.exceptions)
    if args.cmd == "report":
        print(render(items))
        return 0
    print(render(items), file=sys.stdout if not items else sys.stderr)
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
