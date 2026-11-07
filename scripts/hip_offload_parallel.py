#!/usr/bin/env python3
"""Compile a multi-arch HIP translation unit with one process per GPU target.

ROCm clang 20 (roc-7.0.0) accepts several ``--offload-arch=`` flags and then
runs the device compile for each architecture one after another. It has no
``--offload-jobs`` flag. ``clang++ -###`` prints that plan. Device jobs for
different architectures write different outputs, so this launcher runs those
groups at once, then the offload bundler and the host compile in order.

CMake invokes it as ``hip_offload_parallel.py <compiler> <args...>``
(``CMAKE_HIP_COMPILER_LAUNCHER`` / ``CMAKE_CXX_COMPILER_LAUNCHER``).
A command with fewer than two offload architectures is executed unchanged.
Set ``HIP_PARALLEL=0`` to force that path. ``HIP_PARALLEL_JOBS`` caps how many
device jobs run at once across every launcher in the build (default: nproc).
"""
from __future__ import annotations

import fcntl
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def _arch(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "-target-cpu" and i + 1 < len(argv) and argv[i + 1].startswith("gfx"):
            return argv[i + 1]
        mark = "mcpu=gfx"
        at = arg.find(mark)
        if at >= 0:
            return arg[at + len("mcpu=") :].split(",")[0]
    return None


def _jobs(text: str) -> list[list[str]]:
    found = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('"'):
            found.append(shlex.split(stripped))
    return found


class _Slots:
    """Cross-process cap so ninja -j and per-arch fan-out share one budget."""

    def __init__(self, n: int) -> None:
        self.n = max(1, n)
        self.dir = "/tmp/hip-parallel-slots"
        os.makedirs(self.dir, exist_ok=True)

    def run(self, argv: list[str]) -> int:
        while True:
            for i in range(self.n):
                handle = open(os.path.join(self.dir, str(i)), "a+")
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    handle.close()
                    continue
                try:
                    return subprocess.run(argv).returncode  # proc-allow: raw compiler exit code for the slot budget; policy seam is runtime-PATH, not toolchain launch
                finally:
                    handle.close()
            time.sleep(0.05)


def _run_seq(slots: _Slots, jobs: list[list[str]]) -> int:
    for job in jobs:
        rc = slots.run(job)
        if rc:
            return rc
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: hip_offload_parallel.py <compiler> [args...]")
    compiler, args = sys.argv[1], sys.argv[2:]
    archs = [a.split("=", 1)[1] for a in args if a.startswith("--offload-arch=")]
    plain = os.environ.get("HIP_PARALLEL") == "0" or "-c" not in args or len(archs) < 2
    if plain:
        os.execvp(compiler, [compiler, *args])
    probe = subprocess.run([compiler, "-###", *args], capture_output=True, text=True)  # proc-allow: clang -### plan probe; toolchain dry-run, raw stderr parse, not a runtime policy call
    jobs = _jobs(probe.stderr)
    bundler_at = next((i for i, job in enumerate(jobs) if any("clang-offload-bundler" in a for a in job)), None)
    if not jobs or bundler_at is None:
        os.execvp(compiler, [compiler, *args])
    groups: dict[str, list[list[str]]] = {}
    order: list[str] = []
    for job in jobs[:bundler_at]:
        key = _arch(job)
        if key is None:
            rc = subprocess.run(job).returncode  # proc-allow: ungrouped (non-arch) HIP device job; raw compiler exit for early abort, not a runtime policy call
            if rc:
                sys.exit(rc)
            continue
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(job)
    slots = _Slots(int(os.environ.get("HIP_PARALLEL_JOBS") or os.cpu_count() or 8))
    workers = min(len(order), slots.n) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_seq, slots, groups[key]) for key in order]
        for future in as_completed(futures):
            rc = future.result()
            if rc:
                sys.exit(rc)
    for job in jobs[bundler_at:]:
        rc = subprocess.run(job).returncode  # proc-allow: offload bundler + host compile in order; raw compiler exit for early abort, not a runtime policy call
        if rc:
            sys.exit(rc)


if __name__ == "__main__":
    main()
