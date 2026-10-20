#!/usr/bin/env python3
"""Scan what could be COMMITTED, not everything on disk (issue #382).

`gitleaks dir` walks the filesystem and honours no `.gitignore`, so pointing it at the checkout also
reads build artifacts nobody can commit — `tests/__pycache__/*.pyc` carries the suites' own deliberate
sentinels, so `make secret-scan` reported two findings on a tree with no uncommitted change and printed
the "rotate the key" remediation. CI stayed green only because a fresh runner has no cache; the human
running the documented command got the false alarm.

So the scan reads the **committable set**: `git ls-files -c -o --exclude-standard` — tracked files
plus the untracked files that are not ignored, which is exactly what `git add` would take. The set is
exported to a temporary tree and the SAME pinned gitleaks image and the SAME `.gitleaks.toml` are
pointed at that tree, so the rules and allowlists stay the ones under review.

Nothing here prints a file's content: gitleaks runs with `--redact`, and this script prints only the
scanner's own verdict plus a file COUNT.

Usage:
    python3 scripts/secret_scan.py                 # scan the committable set of this checkout
    python3 scripts/secret_scan.py --list          # print the set (one path per line), scan nothing
    python3 scripts/secret_scan.py --runtime nerdctl
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
#: The scanner image, pinned: the test image has no container engine inside, so the scanner cannot
#: live in it, and a floating tag would silently change the rules between runs.
GITLEAKS_IMAGE = "ghcr.io/gitleaks/gitleaks:v8.30.1"
CONFIG = ".gitleaks.toml"


def committable(root: Path = REPO) -> list[str]:
    """The paths `git add` could take: tracked files + untracked files that are not ignored.

    `-c` cached (tracked, including deleted-but-staged), `-o` others (untracked), and
    `--exclude-standard` applies the ignore rules — including `.gitignore`, `.git/info/exclude` and
    the user's global ignore, so the answer matches what the repository would actually accept.
    """
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-c", "-o", "--exclude-standard"],
                         capture_output=True, text=True, check=True)
    return sorted({name for name in out.stdout.split("\0") if name})


def export(root: Path, dest: Path, names: list[str]) -> int:
    """Copy `names` from `root` into `dest`, preserving the relative layout. Returns the count copied.

    A file that disappeared between the listing and the copy is skipped (a scan is a snapshot, not a
    transaction); a symlink whose target resolves outside the checkout is skipped too, so the export
    cannot pull content in from outside the repository under review.
    """
    copied = 0
    for rel in names:
        src = root / rel
        try:
            if not src.is_file():
                continue
            if src.is_symlink():
                resolved = src.resolve()
                if root.resolve() not in resolved.parents and resolved != root.resolve():
                    continue
            dst = dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        except OSError:
            continue
    return copied


def scan(runtime: str, target: Path, *, image: str = GITLEAKS_IMAGE, config: str = CONFIG) -> subprocess.CompletedProcess:
    """Run the pinned scanner over `target`, mounted at /repo, with the repository's config."""
    return subprocess.run(
        [runtime, "run", "--rm", "-v", f"{target}:/repo:rw", "-w", "/repo", image,
         "dir", "/repo", "--config", f"/repo/{config}", "--redact", "--no-banner", "--exit-code", "1"],
        capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan the committable set of the working tree.")
    ap.add_argument("--root", default=str(REPO), help="the checkout to read (default: this repository)")
    ap.add_argument("--runtime", default="docker", help="the container runtime (docker or nerdctl)")
    ap.add_argument("--list", action="store_true", help="print the committable set and exit")
    ap.add_argument("--image", default=GITLEAKS_IMAGE, help="the scanner image (pinned by default)")
    ap.add_argument("--config", default=CONFIG,
                    help="the gitleaks config, relative to the checkout (must be in the committable set)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    names = committable(root)
    if args.list:
        print("\n".join(names))
        return 0

    with tempfile.TemporaryDirectory(prefix="llgenie-secret-scan.") as tmp:
        dest = Path(tmp).resolve()
        copied = export(root, dest, names)
        # The config must be IN the scanned tree: gitleaks resolves the allowlist paths relative to the
        # tree it walks. It is a tracked file, so the export carries it — assert that instead of trusting.
        if not (dest / args.config).is_file():
            print(f"[secret-scan] FATAL: {args.config} is not in the committable set — the scan would "
                  f"run with no rules; refusing to report a verdict.", file=sys.stderr)
            return 2
        try:
            result = scan(args.runtime, dest, image=args.image, config=args.config)
        except FileNotFoundError:
            print(f"[secret-scan] FATAL: the container runtime {args.runtime!r} was not found. The scan "
                  f"cannot run, and a scan that cannot run must never read as clean.", file=sys.stderr)
            return 2

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    print(f"[secret-scan] scanned the committable set: {copied} file(s) of {len(names)} listed "
          f"(tracked + untracked, ignored paths excluded).")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
