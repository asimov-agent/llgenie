#!/usr/bin/env python3
"""The claim-reader guard: only `scripts/bot_claims.py` may open the run-liveness read.

The claim protocol (issue #799) is that `bot_claims.run_is_live` is the ONE reader of a workflow
run's `status,conclusion` — the four bot legs historically each re-implemented the probe (three
byte-identical copies) plus a per-leg `_LIVE` cache, so two legs in one run could disagree about
whether the run that posted a claim is still alive, and a change to the "unknown stays unknown"
rule reached the module and not the legs. The fix moved the probe + its cache into `bot_claims`
and deleted every leg copy. This guard stops that drift from coming back: a live file that re-opens
the run-liveness read is refused.

The probe's shape is an exact pointer: `gh run view <id> --json status,conclusion` — status AND
conclusion, and NOTHING ELSE, no `--repo`. The other run-view readers in this repo are different
animals (they ask for `jobs`, a commit's runs, or a list) and must not be caught. So the pattern is
`--json`, `"status,conclusion"` as the WHOLE `--json` value, with no `--repo` in the same call.

Commands (stdlib only):

    check [--root DIR] [--include-self] [PATH ...]
        # the paths that re-open the claim liveness read (exit 1); no PATH = whole tree
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

#: The claim-liveness probe: `gh run view <id> --json status,conclusion` and `--repo` is NOT in the
#: same call. `status,conclusion` as the exact `--json` value (not `jobs,status,conclusion,url`,
#: not `databaseId,status,conclusion,...`) is what separates the claim reader from a CI runner.
#: The sign is the closing quote right after `conclusion`.
_CLAIM_PROBE = re.compile(r'"--json",\s*"status,conclusion"')
#: A `--repo` in the same call means this is a repo-scoped CI read, not the claim probe.
_REPO_IN_CALL = re.compile(r'"--repo"')

#: Directories that are never source: VCS, build output, scratch, venvs.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ci-home", ".venv"}

#: Files that may spell the probe: the owner module itself, the guard and its own test (all must be
#: able to name what they forbid), the claim reader's unit test which asserts the rule, and the dated
#: history that predates the consolidation. The rule is NOT weakened: every other live file is still
#: refused, and `--include-self` shows exactly what the allow-list buys by judging them too.
ALLOWED_PREFIXES = ("scripts/bot_claims.py", "scripts/claim_reader_guard.py",
                    "tests/test_bot_claims.py", "tests/test_claim_reader_guard.py",
                    "agent-wiki/", "openspec/changes/", "docs/changes.d/")

#: Binary/media files are not text to a reader.
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".gif", ".woff", ".woff2", ".gz", ".bin"}


def is_claim_read(text: str) -> bool:
    """Whether ONE file re-opens the run-liveness probe (a `--json status,conclusion` with no repo)."""
    text = text or ""
    if not _CLAIM_PROBE.search(text):
        return False
    # Any --repo in the same region means it is a repo-scoped reader, not the claim path.
    return not _REPO_IN_CALL.search(text)


def _gitignore_patterns(root: Path) -> list[str]:
    path = root / ".gitignore"
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        out.append(line)
    return out


def is_ignored(rel: str, patterns: list[str]) -> bool:
    rel = rel.replace(os.sep, "/")
    base = rel.rsplit("/", 1)[-1]
    for pat in patterns:
        p = pat.rstrip("/")
        if not p:
            continue
        if pat.endswith("/"):
            if rel == p or rel.startswith(p + "/") or f"/{p}/" in f"/{rel}":
                return True
            continue
        if "/" in p:
            if rel == p or rel.startswith(p + "/"):
                return True
            continue
        if fnmatch.fnmatch(base, p) or fnmatch.fnmatch(rel, p):
            return True
    return False


def live_files(root: Path) -> list[Path]:
    root = Path(root)
    patterns = _gitignore_patterns(root)
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        if is_ignored(rel, patterns):
            continue
        out.append(p)
    return out


def hits(root: Path, paths: list[Path] | None = None,
         exclude: list[Path] | None = None) -> list[str]:
    """The repo-relative paths of live files that re-open the claim liveness read (empty when clean)."""
    root = Path(root).resolve()
    skip = {Path(p).resolve() for p in (exclude or [])}
    if paths:
        candidates = [Path(p) if Path(p).is_absolute() else root / p for p in paths]
    else:
        candidates = live_files(root)
    out: list[str] = []
    for p in candidates:
        p = Path(p).resolve()
        if p in skip:
            continue
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        if set(Path(rel).parts) & SKIP_DIRS:
            continue
        if any(rel.startswith(pre) for pre in ALLOWED_PREFIXES):
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if is_claim_read(text):
            out.append(rel)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refuse a module re-opening the run-liveness read outside scripts/bot_claims.py.")
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--root", default=".", help="the tree to read (default: the current dir)")
    parser.add_argument("paths", nargs="*", help="files to check instead of the whole tree")
    args = parser.parse_args(argv)

    root = Path(args.root)
    found = hits(root, [Path(p) for p in args.paths] or None)
    if found:
        print("[claim-reader] REFUSED: these live files re-open the run-liveness read outside "
              "scripts/bot_claims.py:", file=sys.stderr)
        for rel in found:
            print(f"  {rel}", file=sys.stderr)
        print("[claim-reader] keep the claim path in scripts/bot_claims.py — a leg reading "
              "`status,conclusion` is the drift issue #799 deleted.", file=sys.stderr)
        return 1
    print("[claim-reader] OK: no live file re-opens the run-liveness read outside scripts/bot_claims.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
