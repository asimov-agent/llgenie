#!/usr/bin/env python3
"""test-published-engine's orchestration sequence as an entry point (issue #2675).

The `test-published-engine` make target is a thin wrapper that calls this module. The
sequence stays inside make so the engine_test / ARCH_ARGS / CI_HOME seams remain make
macros with their exact expansions; this module reproduces the replaced recipe's usage
guard and the order of the three steps:

    make published-engine-pull     # engine_image.py pull-published $(ARCH_ARGS)
    make test-engine-image         # the build-or-verify stage, exactly as before
    make published-engine-binary   # engine_test-wrapped published-binary pytest + CI_HOME clean

Each `make ...` line is a data element of `MAKE_SEQUENCE` (issue #2675's entry-point
convention): scripts/issue_bot_gates.py and scripts/check_wiring.py read the sequence
from this file, so the gates these targets feed stay wired to the same roster.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

#: The usage guard the recipe's `@test -n "$(ENGINE)" -a -n "$(ARCH)"` line enforced.
USAGE = "Usage: make test-published-engine ENGINE=<id> ARCH=cpu|cuda|rocm|vulkan"

#: The three make steps, in order (issue #2675 sequence convention — quoted make commands).
MAKE_SEQUENCE = (
    "make published-engine-pull",
    "make test-engine-image",
    "make published-engine-binary",
)


def sequence_targets() -> list[str]:
    """The make targets this entry point runs, in order (issue #2675 sequence seam)."""
    return [line.split()[1] for line in MAKE_SEQUENCE]


def main(argv: list[str] | None = None) -> int:
    make = os.environ.get("MAKE", "make")
    ap = argparse.ArgumentParser(description="Verify a published engine image (issue #102).")
    ap.add_argument("--engine", default="", help="engine id (make ENGINE)")
    ap.add_argument("--arch", default="", help="cpu|cuda|rocm|vulkan (make ARCH)")
    args = ap.parse_args(argv)
    if not args.engine or not args.arch:
        print(USAGE, file=sys.stderr)
        return 1
    for target in sequence_targets():
        rc = subprocess.call([make, target, f"ENGINE={args.engine}", f"ARCH={args.arch}"])
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
