# engine-build-vllm-cpu-only-default

## ADDED Requirements

### Requirement: the default whole-set sweep is vllm CPU-only

The `matrix()` default sweep (`ARCH=` empty, i.e. `make engine-build-matrix` with `ARCH=""`)
MUST NOT emit a vllm `cuda` or `rocm` cell; it MUST emit the vllm `cpu` cell. A per-engine
default-variant list MUST confine vllm to `cpu` when `arch=""`. No other engine's default sweep is
changed.

WHEN `matrix(arch="")` includes the vllm engine
THEN the emitted vllm rows are exactly `{cpu}` — no `cuda`, no `rocm`.

#### Scenario: default vllm matrix is cpu only

- **Given** `scripts/engine_image.py` `matrix()` with the engine default-variant list (vllm → cpu)
- **When** the whole-set sweep is computed with `arch=""`
- **Then** the vllm rows are exactly `{("vllm","cpu")}` — `cuda` and `rocm` are absent
- **Test:** the engine-matrix unit suite asserts `{("vllm","cpu")}` and that
  `("vllm","cuda")` / `("vllm","rocm")` are not in the default rows

### Requirement: an explicit ARCH= still builds the vllm GPU cell

Passing `arch=cuda` or `arch=rocm` MUST emit the vllm cell for exactly that variant, as today — a
GPU vllm build remains possible when explicitly requested. The existing empty-`arch` filter logic is
unchanged for the non-default (explicit-arch) path.

WHEN `matrix(arch="cuda")` or `matrix(arch="rocm")` includes the vllm engine
THEN the emitted vllm rows include exactly that GPU variant.

#### Scenario: explicit cuda and rocm builds still work

- **Given** the same `matrix()` with the engine default-variant list
- **When** `arch="cuda"` is passed
- **Then** the vllm rows include `("vllm","cuda")`
- **Test:** the engine-matrix unit suite asserts `("vllm","cuda")` (and `("vllm","rocm")` for
  `arch="rocm"`) are present in the explicit-arch rows
