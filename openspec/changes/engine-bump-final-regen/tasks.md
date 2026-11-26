## 1. Producer fix

- [x] 1.1 Add the final generation gate to `scripts/engine_bump.py::bump` (check-engine-params → one
      re-regen → re-check → hard-fail), reporting the final regen's paths in the `regen:` line (proven: python3 -m pytest tests/test_engine_bump.py -q rc=0 at head 3d22efe17).
- [x] 1.2 Unit tests: a desynced tree is caught and re-regenerated (green commit), and a
      non-converging regen hard-fails the bump naming the checker verdict (proven: python3 -m pytest tests/test_engine_bump.py -q rc=0 at head 3d22efe17).

## 2. Re-arm the red lane

- [x] 2.1 Push the regenerated `containers/engines/binaries.json` onto `chore/engine-bump-ollama`
      (the #3029 branch); `make check-engine-params` rc=0 at the new head (proven: make check-engine-params rc=0 at head f6a8e0d02, lane re-armed at head b75eb49ab).

## 3. Verify

- [x] 3.1 `make test-unit` rc=0 with zero skips at the branch head (proven: make test-unit rc=0, 4526 passed, 13638 deselected, 0 skipped in 1418.18s at head 3d22efe17).
- [x] 3.2 `make lint`, `make check-wiring`, `make check-docs`, `make check-ci-discipline`,
      `make openspec-validate NAME=<change>` rc=0 (proven: make lint rc=0, make check-wiring rc=0, make check-docs rc=0, make check-ci-discipline rc=0, make openspec-validate NAME=engine-bump-final-regen rc=0 at head 3d22efe17).
- [x] 3.3 `make lane-preflight` prints `preflight: OK` (proven: make lane-preflight rc=0 printing `preflight: OK (7 gate(s))` at this head).
