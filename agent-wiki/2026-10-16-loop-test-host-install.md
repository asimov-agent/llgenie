# 2026-10-16 — loop-test-host-install (#317)

## The defect

`make loop`'s `test` stage is red on every **Linux** host, for a reason unrelated to the change under
test. `make test` ran `tests/test_install.py` through `$(TEST_RUN)`, which on Linux is
`docker run … -e HOME=/root`; the install tests resolve their artifacts from `HOME`
(`tests/conftest.py`: `BIN = HOME / "bin"`, `MODELS_ROOT = HOME / "models"`), so they asserted
`/root/bin/llgenie` inside a `--rm` container that can never hold a host install. Under the no-skip
policy those six assertions failed loudly.

Measured on `main` `29080c7`, in a clean worktree: `make test-install` → `6 failed, 1 passed`. In
`make loop` on `08f585f`: the same six, with `330 passed` in the stage and every other stage green.

## The fix

- `make test` no longer names `tests/test_install.py` in its containerized command. The hermetic files
  stay in `$(TEST_RUN)`; the install assertions run through `$(MAKE) test-install-host`, which runs them
  with the host's `$(PY)` against the real `~/bin/llgenie` and `~/models`.
- Nothing is dropped: the same six assertions run in `make test`, in the loop's `install` stage, and via
  `test-install-ci` in CI. On macOS `test-install-host` runs the same command with the same venv python,
  so both OSes now run identical assertions — only the interpreter's location differs.
- `tests/test_loop_test_stage.py` pins the contract: the containerized command must not name the install
  tests, `test` must call `test-install-host`, that target must use `$(PY)` and not `$(TEST_RUN)`, and
  some gate must still name the file. Wired into `make test-unit`, so it cannot regress silently.

## Verification

- `make openspec-validate NAME=loop-test-host-install` → valid.
- `make lint`, `make check-wiring`, `make check-docs` → see the PR's checks.
- The loop gate itself is the proof: `make loop` on a Linux host with a real `make install` goes green
  end to end — the `test` stage included.

## Status

Implemented in the `fix/loop-test-linux` branch; PR pending. Closes #317.

Related: #296 / #299 (the `make loop` run that verified #296 is what surfaced this) and #305 (a
different defect in the same tooling, filed and not folded in here).
