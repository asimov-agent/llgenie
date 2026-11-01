# sglang/cuda prebuilt vs the guards that still demand install steps (#1306)

**Issue:** #1306 · **PR:** this change's PR · **Branch:** `agent/issue-1306-sglang-cuda-guards`

## Problem

`linux/unit` was RED on `main@dd8792d1` (also red at `d5b58d85`): 12 tests failed, all on the
same self-contradiction shipped by #1250 (`ddac5490`). The sglang/cuda SKILL was set to
`prebuilt: true` (zero install steps — the correct, OOM-safe path: its source AOT
`fp8_gemm_kernel.cu` nvcc pass OOM-kills at every arch set and thread cap), but the peer guards
that shipped in the same merge still demanded steps for the cuda backend:

- `skills-validate` (`scripts/engine_skills.py::validate`) reported `no install steps for backend
  cuda` — it never shared the renderer's `if prebuilt: steps=[]` special-case.
- `tests/test_engine_skills.py::test_sglang_cuda_install_uses_uv_not_pip` asserted a `uv pip
  install` step for a backend that is legitimately prebuilt (its recipe is empty).
- `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases` asserted `FROM
  lmsysorg/sglang:v0.5.22` was NOT in the cuda Dockerfile — but a prebuilt cell starts exactly
  FROM that image.
- The source-guard census still counted one prebuilt cell; sglang/cuda's restoration makes two.

## What changed

1. `scripts/engine_skills.py::validate`: a backend whose container spec is `prebuilt: true` no
   longer fires the "no install steps for backend B" error — the validator and renderer now share
   the same prebuilt special-case (`(container_spec(s, b) or {}).get("prebuilt")` → continue).
2. `tests/test_engine_skills.py::test_sglang_cuda_install_uses_uv_not_pip` →
   `test_sglang_cuda_install_is_consistent_with_its_prebuilt_flag`: asserts BEHAVIOUR. Prebuilt →
   zero install steps + validator-clean (the "no install steps for backend cuda" path must not
   fire). Source → the uv-not-pip assertions (uv bootstrap, `.[all]` not `python[all]`,
   wheel_stub/scikit-build-core/cmake preinstall, `-DSGL_KERNEL_COMPILE_THREADS`). Passes on `main`
   without being weakened into a no-op.
3. `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`: sglang/cuda now
   asserts `FROM lmsysorg/sglang:v0.5.22` with no install steps; sglang/rocm still compiles.
4. `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`: census moves
   to 29 source / 2 prebuilt.

## What was verified

- `tests/test_engine_skills.py test_engine_skill_gap.py test_engine_source_guard.py
  test_registry_sync_trend.py` → 198 passed (the previously-red suites).
- `make skills-validate` → `[skills-validate] 16 skills, registry 16 engines, 0 error(s)`.
- `make check-engine-source` → OK: 29 prebuilt=false run their own build; 1 tracked (litert/cpu #615).
- `make check-engine-coverage`, `make check-engine-params` green.
- `make ci-unit` (the `linux/unit` pipeline job) → green at the PR head, run named in the PR body.

## Not covered

- The OOM itself — already a dated decision in the SKILL comment, not re-litigated.
- #673 (broader unfrozen-store engine-skill-gap) — separate tracking remains.
