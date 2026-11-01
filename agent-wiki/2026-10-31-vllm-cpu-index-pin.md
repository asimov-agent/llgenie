# vllm/cpu build-engine fails — the pinned torch needs the pytorch cpu index (#1241)

**Issue:** #1241 · **PR:** this change's PR · **Branch:** `fix/1241-vllm-torch-pin`

## Problem

`make build-engine ENGINE=vllm ARCH=cpu` failed at `Dockerfile.cpu` [5/5]
(`python3 engine_runner.py install params.json`): the committed vllm pin's
`requirements/build/cpu.txt` requests `torch==2.13.0+cpu`, a **local-version wheel**
served only by the pytorch cpu repack index (`download.pytorch.org/whl/cpu`) — stock
PyPI has no `+cpu` wheel. With `--index-strategy unsafe-best-match` against PyPI, uv
reports `No solution found when resolving dependencies: ╰─▶ Because there is no version
of torch==2.13.0+cpu ... your requirements are unsatisfiable.` → `[engine-runner] FAIL
vllm/cpu: step exited 1` (`Makefile:1227`, engine-build run 41245076650 @ `abc1d3ac`).
Only the cuda row preinstalled torch (from the `cu130` index); the cpu and rocm rows
didn't preinstall at all, so their `-r *.txt` never resolved.

## What changed

1. `skills/engines/vllm/SKILL.md` + regenerated `containers/engines/params/vllm.json`:
   the **cpu** row now preinstalls `uv pip install --system --break-system-packages
   torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu` BEFORE its
   `-r requirements/build/cpu.txt` — exact mirror of the cuda row's `cu130` preinstall.
   Verified satisfiable against the real index: `uv pip install torch==2.13.0 --index-url
   .../whl/cpu --dry-run` resolves to **`torch==2.13.0+cpu`** — the exact wheel cpu.txt
   demands.
2. Added `tests/test_engine_skills.py::test_vllm_cpu_preinstalls_torch_from_the_cpu_index_before_cpu_txt`:
   pins the cpu torch preinstall carries `--index-url https://download.pytorch.org/whl/cpu`
   and comes BEFORE the `cpu.txt` row.

## rocm is a separate, documented upstream-pin mismatch (NOT fixed here — honest scope)

The **rocm** row also reds, but for a distinct reason: its pinned `requirements/build/
rocm.txt` requests `torch==2.12.0+rocm7.14.0`, which **no reachable pytorch rocm index
serves** (rocm7.1 serves `+rocm7.1`; rocm6.2/7.0/7.2 serve other tags; there is no
`rocm7.14.0`). Verified: `uv pip install torch==2.12.0+rocm7.14.0 --index-url .../whl/<each>`
is unsatisfiable on every index probed. That is an upstream vllm-pin / build-tag problem
(what torch+rocm build to publish and from where) — a params-only preinstall cannot fix
it, unlike cpu. It is out of this PR's changed-vehicle scope and recorded here + on the
issue rather than shipped as a half-fix. cpu is the measured primary cell and is fully
fixed.
