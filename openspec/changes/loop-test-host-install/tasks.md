# loop-test-host-install — tasks

Issue: [#317](https://github.com/asimov-agent/llgenie/issues/317)

## 1. Fix the wiring

- [x] 1. Move `tests/test_install.py` out of the containerized command in `test:` and delegate it to
      `$(MAKE) test-install-host`, so the install assertions run on the host where the artifacts are.
- [x] 2. Keep the hermetic files in `$(TEST_RUN)`, so the containerized half is unchanged.

## 2. Pin the contract

- [x] 3. Add `tests/test_loop_test_stage.py`: the containerized command must not name
      `tests/test_install.py`, `test` must call `test-install-host`, `test-install-host` must run the
      install tests with `$(PY)` and not `$(TEST_RUN)`, and some gate must still name the file.
- [x] 4. Wire the new test into `make test-unit` (and thus into the loop's `unit` stage), so the
      contract is enforced by a gate and `check-wiring` sees it.

## 3. Verify

- [x] 5. `make test-unit` exits 0 with the new test included.
- [x] 6. `make test` exits 0 on a Linux host with a real `make install` — the stage the loop runs.
- [x] 7. `make lint`, `make check-wiring`, `make check-docs`, `make check-dispatch-forms` and
      `make openspec-validate NAME=loop-test-host-install` exit 0.
- [x] 8. The loop gate goes GREEN end to end: `make loop` with all 13 stages passing on a Linux host.
