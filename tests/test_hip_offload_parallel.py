"""The vLLM ROCm launcher reads a clang -### plan and groups it by GPU target.

The script is installed into the engine image from scripts/hip_offload_parallel.py.
ROCm clang 20 compiles every --offload-arch in one process; the launcher runs the
per-arch device jobs concurrently. These checks lock the plan parser, which is the
part that decides what may run at the same time.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/hip_offload_parallel.py"
spec = importlib.util.spec_from_file_location("hip_offload_parallel", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_arch_comes_from_the_device_cpu_or_the_linker_mcpu():
    assert mod._arch(["clang-20", "-target-cpu", "gfx1100", "-emit-obj"]) == "gfx1100"
    assert mod._arch(["ld.lld", "-plugin-opt=mcpu=gfx942"]) == "gfx942"
    assert mod._arch(["clang-20", "-cc1", "-triple", "x86_64-unknown-linux-gnu"]) is None


def test_jobs_are_the_quoted_driver_lines_only():
    dump = "\n".join([
        "AMD clang version 20",
        ' "/opt/rocm/lib/llvm/bin/clang-20" "-cc1" "-target-cpu" "gfx1100"',
        ' "/opt/rocm/lib/llvm/bin/clang-offload-bundler" "-type=o"',
        "not a job",
    ])
    jobs = mod._jobs(dump)
    assert len(jobs) == 2
    assert jobs[0][0].endswith("clang-20")
    assert jobs[0][jobs[0].index("-target-cpu") + 1] == "gfx1100"
    assert "clang-offload-bundler" in jobs[1][0]
