#!/usr/bin/env python3
"""test-clean's orphaned-container sweep as an importable entry point (issue #2675).

The `test-clean` make target is a thin wrapper that calls this module. The sweep is
Docker/nerdctl-agnostic, exactly as the recipe it replaced was: list every container,
keep only the ones whose image reference contains the test-image marker, and remove
ONLY the stopped/left-over ones — never a currently-running test (e.g. an in-progress
health check). The base recipe's quirks are preserved verbatim:

- never uses `--filter ancestor` (docker lacks it),
- the image test greps the raw `inspect -f '{{.Image}}'` output for `llgenie/test`
  (an in-progress container whose inspect fails yields "" and is skipped),
- the running test greps the lowercase-insensitive output of `inspect -f
  '{{.Running}}'` for `false` (an inspect failure yields "false", i.e. remove).
"""
from __future__ import annotations

import argparse
import subprocess
import sys

#: Substring the container's image reference must contain to be a test-image container.
TEST_IMAGE_MARKER = "llgenie/test"


def _inspect(runtime: str, fmt: str, container: str, fallback: str) -> str:
    """`<runtime> inspect -f <fmt> <container>`; on failure, `fallback` (the shell's `|| echo`)."""
    proc = subprocess.run([runtime, "inspect", "-f", fmt, container],
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else fallback


def sweep(runtime: str, marker: str = TEST_IMAGE_MARKER) -> list[str]:
    """Remove stopped containers whose image reference names the test image; return their ids."""
    listed = subprocess.run([runtime, "ps", "-a", "-q"], capture_output=True, text=True)
    removed: list[str] = []
    for container in listed.stdout.split():
        if marker not in _inspect(runtime, "{{.Image}}", container, ""):
            continue
        if "false" in _inspect(runtime, "{{.Running}}", container, "false").lower():
            subprocess.run([runtime, "rm", "-f", container], capture_output=True)
            removed.append(container)
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Remove stopped llgenie test-image containers.")
    ap.add_argument("--runtime", default="docker", help="container CLI (make RUNTIME)")
    ap.add_argument("--test-img", default="llgenie/test:latest",
                    help="test image name for the closing report (make TEST_IMG)")
    args = ap.parse_args(argv)
    sweep(args.runtime)
    print(f"Pruned stopped orphaned {args.test_img} containers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
