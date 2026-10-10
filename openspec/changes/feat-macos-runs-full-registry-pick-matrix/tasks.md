## 1. Verify the macOS coverage

- [x] 1.1 Confirm `tests/test_pick_full_registry.py` is in the shared `make test-unit` line (runs on both OSes).
- [x] 1.2 Confirm the CI `unit` job runs `make ci-unit` on both `ubuntu-latest` and `macos-15-intel` (the same `pipeline.yml` called twice).
- [x] 1.3 Confirm the arch parametrization includes `metal` (driven through the `LLAMA_BACKEND` env seam, not the runner's real hardware).
- [x] 1.4 Confirm the conftest no-skip guard turns any skipped test into a loud failure, so macOS coverage cannot silently drop.

## 2. Document the guarantee

- [x] 2.1 `proposal.md` records that the full-registry pick-matrix business-logic tests run on macOS CI with the metal arch and its variants, same as Linux.
- [x] 2.2 `specs/pick-matrix-macos/spec.md` adds the ADDED requirement + scenarios locking the macOS coverage.

## 3. Verify (the loop gate)

- [x] 3.1 `make lint`, `make openspec-validate NAME=feat-macos-runs-full-registry-pick-matrix`, and every task above ticked.
