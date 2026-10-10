#!/usr/bin/env python3
"""`make ci-engines BACKEND=<b>`: the ONE engine-install stage of the pipeline (issue #120).

Linux and macOS run the same `make ci-<job>` targets; they diverge only in the engine
matrix. This script is that matrix row, with one entrypoint for both OSes:

  BACKEND=cpu|cuda|rocm|vulkan  container engines (Linux images; the macOS-intel runner
                                runs the same linux images in its Docker VM):
                                  make test-install-published BACKEND=<b>
                                = `make install` pulls this backend's published images,
                                every start script prints its version, llgenie answers "hi".
  BACKEND=metal                 native-Metal engines (Apple Silicon; Metal cannot run in a
                                container, issue #114), installed in their own environment:
                                  make test-native-engines        each native engine is
                                      installed by its skill, prints its version, serves a
                                      tiny model on Metal and answers "hi"
                                  make test-native-engine         TensorFold install/update/reuse
                                  make test-interactive-tensorfold-ci   the interactive pick
                                  make test-native-engine-light   TensorFold's lightest model

Every stage runs; the first failure does not hide the others, and any failure fails the run.

  python3 scripts/ci_engines.py <backend>      # what `make ci-engines BACKEND=<b>` runs
  python3 scripts/ci_engines.py --plan <b>     # print the make targets, run nothing
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys

CONTAINER_BACKENDS = ("cpu", "cuda", "rocm", "vulkan")
NATIVE_TARGETS = ("test-native-engines", "test-native-engine", "test-interactive-tensorfold-ci",
                  "test-native-engine-light")


def plan(backend: str) -> list[list[str]]:
    """The make invocations of the engine stage for ``backend`` (ValueError when unknown)."""
    if backend in CONTAINER_BACKENDS:
        return [["test-install-published", f"BACKEND={backend}"]]
    if backend == "metal":
        return [[t] for t in NATIVE_TARGETS]
    raise ValueError(f"BACKEND must be one of {', '.join(CONTAINER_BACKENDS)}, metal; got {backend!r}")


def apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def real_main(argv: list[str]) -> int:
    dry = argv[:1] == ["--plan"]
    args = argv[1:] if dry else argv
    backend = (args[0] if args else os.environ.get("BACKEND", "")).strip()
    try:
        steps = plan(backend)
    except ValueError as e:
        print(f"[ci-engines] {e}  (usage: make ci-engines BACKEND=<backend>)", file=sys.stderr)
        return 2
    if dry:
        for s in steps:
            print("make " + " ".join(s))
        return 0
    if backend == "metal" and not apple_silicon():
        print(f"[ci-engines] BACKEND=metal needs an Apple-Silicon Mac (this is {platform.system()} "
              f"{platform.machine()}): native Metal engines cannot run in a container", file=sys.stderr)
        return 1
    make = os.environ.get("MAKE", "make")
    failed = []
    for s in steps:
        print(f"==> [ci-engines] {backend}: make {' '.join(s)}", flush=True)
        if subprocess.run([make, *s]).returncode != 0:
            failed.append(" ".join(s))
    print(f"[ci-engines] {backend}: {len(steps) - len(failed)}/{len(steps)} stages green"
          + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(real_main(sys.argv[1:]))
