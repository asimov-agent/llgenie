# Run the full-registry pick-matrix business-logic tests on macOS too (issue #122)

## Why

The system pick-matrix test (`tests/test_pick_full_registry.py`) exercises the whole
llgenie business logic — model → engine (by arch) → highest fitting quant → its exact
HF link — over every (model × engine × arch × vram × ram) permutation, with only the
engine start mocked. It is wired into `make test-unit`, which the CI `unit` job runs on
**both** Linux and macOS (the same `pipeline.yml` is called twice, `ubuntu-latest` and
`macos-15-intel`). The arch axis includes `metal`, so the metal selection logic and its
engine variants are asserted on macOS CI exactly as on Linux. This change documents and
locks that guarantee: the same business-case tests run on macOS, with the metal arch and
its variants, not just on Linux.

## What Changes

- No code change: `tests/test_pick_full_registry.py` (and the other pick-matrix tests)
  are already in the shared `make test-unit` line, which the CI `unit` job runs on both
  OSes. The arch parametrization already includes `metal` (driven through the
  `LLAMA_BACKEND` env seam, not the runner's real hardware), so metal selection is
  asserted on macOS CI too.
- This OpenSpec change records the guarantee and adds a spec scenario + task that lock
  it: the full-registry pick-matrix business-logic tests run on macOS CI with the metal
  arch and its variants, same as Linux.

## Impact

- New: `openspec/changes/feat-macos-runs-full-registry-pick-matrix/specs/pick-matrix-macos/spec.md`.
- No source or test files change (the coverage already exists); this is a
  documentation/verification change so the macOS coverage is explicit and reviewable.
