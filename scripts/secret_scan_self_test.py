#!/usr/bin/env python3
"""Prove the secret scanner works — a planted credential MUST be caught (issue #360).

A scanner that silently does nothing is a false green: `make secret-scan` would exit zero on a tree
that carries a live key, and every reviewer would read that zero as "clean". This script plants a
**fake** credential (a `ghp_` shape that belongs to no account) in a temporary directory, points the
same scanner image and config at it, and fails unless the scan exits non-zero. It then removes the
plant and asserts the same scan is clean, so the exit code cannot be stuck at 1 either.

Nothing is written into the repository: the plant lives under a temp dir, is removed in a `finally`,
and its value is never printed (a scanner's output is redacted, and this script prints only the
verdict).

Usage:
    python3 scripts/secret_scan_self_test.py            # real scanner, real config, planted value
    python3 scripts/secret_scan_self_test.py --docker docker
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / ".gitleaks.toml"
#: A `ghp_`-shaped value that is not a credential: the scanner's own rule for a GitHub PAT fires on
#: the shape, which is exactly what this proves. Never a live token.
PLANT = "ghp_" + "SelfTest0123456789abcdefGHIJKLMNOP"  # 36-char body, like a real PAT


def _scan(docker: str, target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [docker, "run", "--rm", "-v", f"{target}:/scan:rw", "-v", f"{CONFIG}:/cfg.toml:ro",
         "ghcr.io/gitleaks/gitleaks:v8.30.1",
         "dir", "/scan", "--config", "/cfg.toml", "--redact", "--no-banner", "--exit-code", "1"],
        capture_output=True, text=True, timeout=300)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A planted credential must be caught by the scanner.")
    ap.add_argument("--docker", default="docker", help="the container runtime to use (default: docker)")
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        planted = work / "planted.env"
        planted.write_text(f"GITHUB_TOKEN={PLANT}\n")
        try:
            caught = _scan(args.docker, work)
        finally:
            planted.unlink(missing_ok=True)

        if caught.returncode == 0:
            print("[secret-scan-self-test] FATAL: the scanner did NOT catch a planted credential — "
                  "`make secret-scan` is a false green (exit 0 on a tree it should flag).", file=sys.stderr)
            return 1
        if PLANT in (caught.stdout + caught.stderr):
            print("[secret-scan-self-test] FATAL: the scanner printed the planted value unredacted.",
                  file=sys.stderr)
            return 1
        print(f"[secret-scan-self-test] planted credential caught (exit {caught.returncode}), value "
              f"never printed")

        clean = _scan(args.docker, work)
        if clean.returncode != 0:
            print(f"[secret-scan-self-test] FATAL: the same directory is still flagged after the plant "
                  f"was removed (exit {clean.returncode}) — the scan cannot be clean.", file=sys.stderr)
            return 1
        print("[secret-scan-self-test] OK: the planted credential is caught and the clean tree is green.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
