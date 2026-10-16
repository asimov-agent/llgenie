# loop-test-host-install — proposal

Issue: [#317](https://github.com/asimov-agent/llgenie/issues/317)

## Why

`make loop`'s `test` stage is red on every **Linux** host, for a reason that has nothing to do with the
change being verified. `make test` runs `tests/test_install.py` through `$(TEST_RUN)`, which on Linux is
`docker run … -e HOME=/root` (Makefile `TEST_OPTS`). The test resolves its artifacts from `HOME`
(`tests/conftest.py`: `BIN = HOME / "bin"`, `MODELS_ROOT = HOME / "models"`), so it asserts
`/root/bin/llgenie` inside a `--rm` container that can never contain a host install. Under the no-skip
policy those six tests fail loudly.

Measured on `main` `29080c7` (before the #299 merge), in a clean worktree:

```
$ make test-install
E     where is_file = PosixPath('/root/bin/llgenie').is_file
FAILED tests/test_install.py::test_launcher_exists_and_executable
FAILED tests/test_install.py::test_launcher_is_venv_based - FileNotFoundError
FAILED tests/test_install.py::test_llama_ai_symlink_points_at_repo
FAILED tests/test_install.py::test_llama_server_on_path
FAILED tests/test_install.py::test_installed_launcher_lists_at_least_one_model
FAILED tests/test_install.py::test_launcher_dry_run_picks_a_unique_model
6 failed, 1 passed in 0.06s
```

The same six in `make loop` on `08f585f`: `test` FAIL, with `330 passed` in that stage and every other
stage green. The install assertions themselves are fine — `make test-install-host` runs them with the
host's `$(PY)` (`~/llama-gguf-tools/.venv/bin/python`) and passes **7 passed** against a current
`make install`. On macOS the containerized copy does not exist (`TEST_RUN` is the venv python with the
real `HOME`), so nobody saw this: the gate is host-dependent and nothing pins it.

A permanently red stage in the local "done" gate is worse than no stage: it teaches everyone to ignore
the stage, and the artifact assertions it claims to make are already made, correctly, host-side.

## What Changes

- **`make test` asserts the install on the host, where the artifacts are.** The hermetic files stay in
  the container (`$(TEST_RUN)`); `tests/test_install.py` moves out of that command into
  `$(MAKE) test-install-host`, which runs it with the host's gguf venv python — the same way the loop's
  `install` stage and `make ci-install` already do.
- **The assertions still run, and are now assertable.** Nothing is dropped: the same six artifact
  assertions run in `make test`, in the loop's `install` stage, and (via `test-install-ci`) in CI.
- **One code path on both OSes**: on macOS `test-install-host` runs the same command with the same venv
  python, so Linux and macOS run the identical assertions — only the interpreter's location differs,
  exactly as `TEST_RUN` already does for the containerized half.
- **A test pins the contract** (`tests/test_loop_test_stage.py`): the `test` recipe must not name
  `tests/test_install.py` in its containerized command, it must call `test-install-host`, and
  `test-install-host` must name `tests/test_install.py` — so the assertions cannot silently leave the
  gate again.

## Not covered

- #305 — the inline-script check only inspects a workflow's last `run:` block (found while verifying
  #296; its own change).
- #296 — the per-command inline-script check (merged as #299); the `make loop` run that verified it is
  what surfaced this.

Refs: #296, #299, #305.
