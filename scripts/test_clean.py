#!/usr/bin/env python3
"""Prune orphaned left-over `llgenie/test` containers (issue #800 extraction of the test-clean recipe).

The 15-line `test-clean` recipe was a container loop: list all containers, keep the ones referencing
the test image, stop+remove only the stopped/left-over ones (never kill a running test), runtime-
agnostic and deliberately not `--filter ancestor` (docker lacks it). This module owns that loop so
the recipe is one line and the pruning policy is unit-testable.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

#: The image fragment the recipe matched against ($$(RUNTIME) inspect -f '{{.Image}}').
IMAGE_FRAGMENT = "llgenie/test"


def prune(runtime: str, image_fragment: str = IMAGE_FRAGMENT) -> int:
    """Remove stopped orphaned containers referencing `image_fragment`; never touch running ones.

    Returns 0 when no container was killed (only stopped/left-over ones are removed), and 0 also
    on an unreachable runtime (the old recipe's `2>/dev/null` swallowed the ps/inspect errors — an
    absent docker daemon pruned nothing and reported success). Any container still running when the
    loop reads it is left untouched.
    """
    # the recipe listed ALL containers first, then filtered by image — never `--filter ancestor`
    list_cmd = [runtime, "ps", "-a", "-q"]
    try:
        listed = subprocess.run(list_cmd, capture_output=True, text=True)
    except FileNotFoundError:  # the runtime binary is absent -> nothing to prune, like the recipe
        return 0
    containers = [c for c in listed.stdout.split() if c]
    for c in containers:
        info = subprocess.run([runtime, "inspect", "-f", "{{.Image}}", c],
                              capture_output=True, text=True)
        if image_fragment not in info.stdout:
            continue
        running = subprocess.run([runtime, "inspect", "-f", "{{.Running}}", c],
                                 capture_output=True, text=True)
        if "false" in running.stdout.lower():
            subprocess.run([runtime, "rm", "-f", c], capture_output=True, text=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prune stopped orphaned llgenie/test containers (issue #800)")
    ap.add_argument("--runtime", default="docker", help="the container runtime (docker or nerdctl)")
    ap.add_argument("--image", default=IMAGE_FRAGMENT, help="the image fragment to match")
    a = ap.parse_args(argv)
    prune(a.runtime, a.image)
    print(f"Pruned stopped orphaned {a.image} containers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
