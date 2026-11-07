# 2026-11-02 vllm rocm: resolve TheRock `rocm[device-gfx*]` extras from the AMD index (issue #1558)

The vllm rocm `engine-build` cell failed at the editable install:

```
Failed to build `rocm==0.1.0`
  Call to `poetry.core.masonry.api.build_wheel` failed (exit status: 1)
  [stderr] ModuleNotFoundError: No module named 'poetry'
  help: `rocm` (v0.1.0) was included because `vllm` ... depends on `rocm`
```

Measured at the failing run `41402868957` (head `514d45ba`).

## What was actually wrong (measured)

Default PyPI's `rocm==0.1.0` is an AMD-OSS **placeholder** — a 606-byte poetry-built sdist
(`requires_python>=3.12`, no wheel, no `device-*` extras; `pypi.org/pypi/rocm/0.1.0/json`
ownership: `AMD-OSS`). It is NOT the `rocm` the pinned vllm wants. The pinned source
(`v0.33.0` = `4ba787ec`, matching the failing `+g4ba787ec9`) emits per-target TheRock extras —
`rocm[device-gfx<arch>]`, `torch[device-gfx<arch>]`, `torchvision[device-gfx<arch>]` — from
`setup.py::get_rocm_device_requirements()` **only while `rocm_sdk` is importable**. Step 2 of
`install.rocm` (`-r requirements/build/rocm.txt`) installs the real AMD `rocm==7.14.0` (a
setuptools meta-package providing `rocm_sdk`) from `repo.amd.com/rocm/whl-multi-arch/`; so by
step 4 `rocm_sdk` IS importable and the extras MUST resolve from that same AMD index. Step 4's
`uv pip install --no-build-isolation -e .` carried no AMD index, tried the default PyPI, found the
placeholder `rocm==0.1.0`, and `--no-build-isolation` has no poetry → the exact `ModuleNotFoundError`.

So: the resolve was NOT wrong about wen vllm genuinely needs (TheRock device wheels) — it was a
**missing index** on step 4. Class = "the -e . resolver lacked the index the build deps already used".

## Fix

Edit `skills/engines/vllm/SKILL.md` `install.rocm` step 4 (params are generated — never hand-edit
`params/vllm.json`): add to the `-e .` editable install
`--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match` —
the same index/strategy step 2 already uses — so `rocm[device-gfx*]` and the sibling TheRock
device packages resolve from AMD, never PyPI. Regenerate with `make generate-engine-params ENGINE=vllm`
(rocm `install[3]` gains the index args; cuda/cpu untouched).

## Proof

Local uv dry-run in a fresh py3.12 venv:
- WITH the AMD index: `uv pip install --dry-run rocm[device-gfx1100] --extra-index-url
  https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match` →
  `+ rocm==7.14.1`, `+ rocm-sdk-core==7.14.1`, `+ rocm-sdk-device-gfx1100==7.14.1`,
  `+ rocm-sdk-libraries==7.14.1` (no placeholder).
- WITHOUT it (the bug): same command → `+ rocm==0.1.0` plus
  `warning: does not have an extra named device-gfx1100` — the failing class.

`make check-engine-params`, `make check-engine-source`, `make openspec-validate NAME=vllm-rocm-device-extras-index`
green. The `engine-build` vllm arch=rocm runs (`push=false` then `push=true`) are the CI-proof
acceptance of issue #1558 (recorded at their run ids + head shas in the PR).

## CUDA cell on the 16 GiB runner

Run 41696864556 `engine-build-vllm-cuda` died with `make: Killed` and the runner shutdown signal
after about 60 minutes, with no compiler error. The editable install did not set `MAX_JOBS`, so
ninja started one `nvcc` per core on the fat list `75;80;86;89;90;120` and the kernel killed the
build. `install.cuda` now sets `MAX_JOBS=2` and `CMAKE_BUILD_PARALLEL_LEVEL=2`. The 240-minute
cell timeout stays (owner closed #1609).

The pin gate used to be the last step of `linux / unit` and failed on the first 404.
That job's ceiling is 120 minutes, so it cannot sit through a 240-minute engine-build.
`ci.yml`'s `engine-pins` job polls `make check-engine-pins-published WAIT=290` until
the tags resolve. A change that repins nothing still returns immediately.
