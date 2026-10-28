#!/usr/bin/env python3
"""The renamed-module guard: the old CLI name must not come back into a live file (issues #251, #573).

The CLI is `scripts/llgenie_serve.py`. The file next to it under the OLD name stays as a deprecated
alias — and that shim is the only place the old spelling may appear, together with the dated history
(`agent-wiki/`, `openspec/changes/`) and this module (which has to spell the name it forbids). Every
other live text file is refused, `docs/ARCHITECTURE.md` included.

The rule lives HERE rather than inside a test because two things enforce it, and one code path keeps
them from drifting:

  * `make test-unit` (`tests/test_rename_llgenie_serve.py`) — the reviewer;
  * the architecture bot, whose 6-hourly doc refresh wrote the old name into `docs/ARCHITECTURE.md`
    and only found out 25 minutes later, as two red unit jobs on PR #572 (issue #573) — the writer.

So the writer is checked by the same function as the reviewer, before it commits anything.

Commands (stdlib only):

    check [--root DIR] [--include-self] [PATH ...]
        # the paths that name the old module (exit 1); no PATH = whole tree

`make check-module-names` (inside `ci-unit`) runs this CLI, so the rule is executable in CI and not
only asserted in prose (issue #812).
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

#: The old module name, but NOT `llama_server`/`llama-server` (llama.cpp's binary).
OLD_MODULE = re.compile(r"\bllama_serve\b")

#: Directories that are never source: VCS, build output, scratch, venvs.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ci-home", ".venv"}

#: The shim keeps the old name on purpose, history keeps whatever was true then, and this module has
#: to be able to name what it forbids.
ALLOWED_PREFIXES = ("scripts/llama_serve.py", "scripts/module_name_guard.py", "agent-wiki/",
                    "openspec/changes/")

#: Binary/media files are not text to a reader.
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".gif", ".woff", ".woff2", ".gz", ".bin"}

#: Files the CLI must not judge, by reason, because the library's caller excludes them (`hits(...,
#: exclude=...)`). ONE entry: the guard's own test spells the forbidden name in order to assert the
#: rule, so judging it would make the CLI refuse the file that proves the rule — the false red that
#: kept this guard out of every target (issue #812). The rule itself is NOT weakened: every other
#: live file, this module's allowlist aside, is still refused, and `--include-self` shows exactly
#: what the exclusion buys by judging this file too.
SELF_EXCLUDED = ("tests/test_rename_llgenie_serve.py",)


def offenders(text: str) -> list[str]:
    """The old-name spellings in ONE file's text (empty when clean)."""
    return [m.group(0) for m in OLD_MODULE.finditer(text or "")]


def is_clean(text: str) -> bool:
    """Whether ONE text names the old module nowhere."""
    return not offenders(text)


def _gitignore_patterns(root: Path) -> list[str]:
    """The checkout's own `.gitignore` rules (negations noted but not applied — see `live_files`)."""
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
    """True when `rel` matches a `.gitignore` rule: `dir/` prefixes, `*.ext` names, or a literal path.

    A minimal matcher on purpose — the guard needs "is this a file a review would see", not git's
    full semantics — and it works where git does not: the unit suite runs in the test image with the
    checkout mounted at `/workspace`, where `.git` points outside the mount and `git ls-files` fails
    (#350).
    """
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
    """The files a review would see: the tree walk minus what the checkout's `.gitignore` excludes.

    A guard that reads everything judges files git does not track — a bot's gitignored working file
    (`refine-in.md`) reddened the local `make loop` while CI, on a fresh checkout, stayed green
    (issue #350).
    """
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
    """The repo-relative paths of live files that name the old module (empty when clean).

    `paths` restricts the read to those files (relative to `root`, absolute, or repo-relative);
    without it the whole tree is read. `exclude` names files a caller must not judge — the guard's
    own test spells the name it forbids, so it excludes itself rather than weakening the rule. The
    allowed prefixes apply either way, so a caller cannot check itself into a false pass.
    """
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
        if not is_clean(text):
            out.append(rel)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refuse the old CLI module name in a live file.")
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--root", default=".", help="the tree to read (default: the current dir)")
    parser.add_argument("--include-self", action="store_true",
                        help="also judge SELF_EXCLUDED (the guard's own test), which is what the "
                             "exclusion buys: without it the CLI refuses the file that proves the rule")
    parser.add_argument("paths", nargs="*", help="files to check instead of the whole tree")
    args = parser.parse_args(argv)

    root = Path(args.root)
    exclude = [] if args.include_self else [root / p for p in SELF_EXCLUDED]
    found = hits(root, [Path(p) for p in args.paths] or None, exclude=exclude)
    if found:
        print("[module-name] REFUSED: these live files name the retired CLI module:", file=sys.stderr)
        for rel in found:
            print(f"  {rel}", file=sys.stderr)
        print("[module-name] describe the launcher as scripts/llgenie_serve.py; the old spelling "
              "belongs to the deprecated shim and the dated history only (issue #251, #573).",
              file=sys.stderr)
        return 1
    print("[module-name] OK: no live file names the retired CLI module.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
