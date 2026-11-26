## 1. Producer fix

- [ ] 1.1 Add the final generation gate to `scripts/engine_bump.py::bump` (check-engine-params → one
      re-regen → re-check → hard-fail), reporting the final regen's paths in the `regen:` line.
- [ ] 1.2 Unit tests: a desynced tree is caught and re-regenerated (green commit), and a
      non-converging regen hard-fails the bump naming the checker verdict.

## 2. Re-arm the red lane

- [ ] 2.1 Push the regenerated `containers/engines/binaries.json` onto `chore/engine-bump-ollama`
      (the #3029 branch); `make check-engine-params` rc=0 at the new head.

## 3. Verify

- [ ] 3.1 `make test-unit` rc=0 with zero skips at the branch head.
- [ ] 3.2 `make lint`, `make check-wiring`, `make check-docs`, `make check-ci-discipline`,
      `make openspec-validate NAME=<change>` rc=0.
- [ ] 3.3 `make lane-preflight` prints `preflight: OK`.
