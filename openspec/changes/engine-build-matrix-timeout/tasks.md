# engine-build-matrix-timeout — tasks

## Specification Tasks

**Requirement: the engine-build build job's timeout is matrix-aware by variant**

- [x] `.github/workflows/engine-build.yml`: build job `timeout-minutes` =
      `${{ (matrix.variant == 'rocm') && 360 || 240 }}` (rocm 360, others 240).
- [x] Regression test `tests/test_ci_variant_matrix.py::test_engine_build_build_job_timeout_is_matrix_aware`
      reads the timeout, asserts it is the expression keyed on `matrix.variant`,
      and reds on a flat value (verified: 1 passed at fixed tree; red on
      pre-fix `int 240`).
- [x] Change-note trio (agent-wiki note + docs/changes.d fragment + regenerated
      CHANGES.md), per #1123.

## Acceptance Tasks

- [x] `make check-docs check-workflows check-wiring lint` green on the PR.
- [x] Acceptance #2 (a `push=true` vllm/rocm cell COMPLETED-SUCCESS at the raised
      cap) is a post-merge release condition (owner-guarded dispatch #1088), not
      an introducing-PR task; recorded as deferred in the PR body / issue / wiki
      note, not fabricated here.
