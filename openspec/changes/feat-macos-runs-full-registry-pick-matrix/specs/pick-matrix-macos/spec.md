## ADDED Requirements

### Requirement: the full-registry pick-matrix business-logic tests run on macOS CI with the metal arch

The system pick-matrix test (`tests/test_pick_full_registry.py`) MUST run on the macOS
CI `unit` job exactly as on Linux — the same `make test-unit` command, the same test
files, the same asserts — and MUST include the `metal` architecture in its permutation
grid. The arch is driven through the `LLAMA_BACKEND` env seam (not the runner's real
hardware, since no CI runner has a Metal GPU), so the metal selection logic and its
engine variants are asserted on macOS CI identically to Linux. A skipped test is a loud
failure (the conftest no-skip guard), so macOS coverage cannot silently drop.

WHEN the macOS CI `unit` job runs `make test-unit`
THEN `tests/test_pick_full_registry.py` runs with the full (model × engine × arch ×
vram × ram) grid including `metal`, and every offered cell maps to a real fitting HF
quant URL — the same business case as Linux.

#### Scenario: the full-registry pick-matrix test runs on macOS with the metal arch
- **Given** the macOS CI `unit` job (macos-15-intel) running `make test-unit`
- **When** `tests/test_pick_full_registry.py` is collected and run
- **Then** it is not skipped, the `metal` arch is in its permutation grid, and every
  offered (model × engine × metal) cell maps to a real fitting HF quant URL
- **Test:** `tests/test_pick_full_registry.py::test_pick_matrix_any_offer_is_a_real_fitting_hf_url`
  (parametrized over `ARCHES = (cuda, rocm, vulkan, cpu, metal)`), run by the macOS CI
  `unit` job via `make test-unit`

#### Scenario: the metal engine variants are asserted on macOS
- **Given** the macOS CI `unit` job running the arch-permutation test
- **When** the `metal` architecture is exercised through the `LLAMA_BACKEND` seam
- **Then** a metal host never falls back to a cpu image, and metal-native engines are
  offered only on metal
- **Test:** `tests/test_pick_matrix_arch_perms.py::test_metal_never_offers_cpu_image`,
  run by the macOS CI `unit` job via `make test-unit`
