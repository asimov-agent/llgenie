# engine-build-matrix-timeout

## ADDED Requirements

### Requirement: the engine-build build job's timeout is matrix-aware by variant

The build job in `.github/workflows/engine-build.yml` (the engine-build producer's
matrix build cell) MUST size its `timeout-minutes` per matrix variant so the heavy
GPU/rocm cell can finish a legitimately-slow build while cheap cells keep a tight
fast-fail budget. `matrix.variant` is the emitted matrix column.

The timeout MUST be `${{ (matrix.variant == 'rocm') && 360 || 240 }}`:
- `rocm` cells get `360` minutes (~3.4× the measured completed-success max of
  ~107 m, per #1818/#1694's "2× the band plus headroom" rule);
- every other variant (`cuda`, `cpu`, `vulkan`, and the `none` guard row) keeps
  `240` minutes.

Capacity only: the change MUST NOT weaken `ci-verdict`, `ci-scope`, or `make
build-engine`.

WHEN the engine-build workflow builds a matrix cell
THEN rocm cells have a 360 m cap and every other variant a 240 m cap, and no gate
is weakened.

#### Scenario: the timeout is an expression keyed on matrix.variant

- **Given** `.github/workflows/engine-build.yml`
- **When** the build job's `timeout-minutes` is read
- **Then** it is the matrix-aware expression `${{ (matrix.variant == 'rocm') && 360 || 240 }}`,
  not a flat integer, and it keys on `matrix.variant`
- **Test:** `tests/test_ci_variant_matrix.py::test_engine_build_build_job_timeout_is_matrix_aware`

#### Scenario: rocm is an emitted variant so the branch is reachable

- **Given** the emitted matrix (`make -s engine-build-matrix`, job build's matrix)
- **When** the variant column is read
- **Then** `rocm` is among `{cpu, cuda, rocm, vulkan}`, so the rocm→360 branch fires
- **Test:** `tests/test_ci_variant_matrix.py::test_engine_build_build_job_timeout_is_matrix_aware`

#### Scenario: a flat timeout (the pre-fix shape) reds the regression test

- **Given** a build job whose `timeout-minutes` is a flat `240`
- **When** the regression test runs
- **Then** the test fails (the `isinstance(expr, str)` / `matrix.variant in expr`
  assertions), proving the guard catches the old flat-wall shape
- **Test:** verified red-on-old / green-on-fixed (pre-fix `timeout-minutes` is
  `int 240`)
