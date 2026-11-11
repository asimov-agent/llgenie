# Install-artifact tests must run on the HOST, not in the containerized `test` stage

`make test` (the loop's `test` stage) runs its pytest list through `$(TEST_RUN)`, which on Linux is
`docker run ... -e HOME=/root`. A test that asserts the real install (`tests/test_install.py` ->
`HOME/bin/llgenie`, `HOME/models`) can therefore NEVER be green in that stage — a `--rm` container with
`HOME=/root` cannot hold a host install, so under the no-skip policy six tests fail loudly on every
Linux host for a reason unrelated to the change being verified. macOS is green only because its
`TEST_RUN` is the venv python with the real `HOME`; the red is host-dependent, so nothing pins it.

## Rules

- **Assert a host install on the host.** Keep the hermetic files in `$(TEST_RUN)`; run the install
  assertions via a host target (`$(MAKE) test-install-host`) that invokes `tests/test_install.py` with
  the gguf venv `$(PY)`, not `$(TEST_RUN)`. This mirrors how `make install` and `ci-install` already
  run host-side.
- **Pin the split with a Makefile-reading test** (no subprocess, no mocks — read the `test:` and
  `test-install-host:` recipes with a regex, anchored on `^target:` so a recipe is never mistaken for
  another target's): assert the containerized line does NOT name `tests/test_install.py`, that it
  calls `$(MAKE) test-install-host`, and that some gate still runs the file. A test that greps the
  recipe catches the exact regression class that otherwise reds silently.
- **Prove a red loop stage is pre-existing before fixing it.** A stage that fails on `main` (measure
  on the pre-merge base commit in a clean worktree, not the feature branch) is environmental or
  host-shaped, not your change; fixing it is a separate issue (`#317`-class), not folded into the
  feature work. When it blocks the loop's local "done" gate, implement it as its own OpenSpec change
  on its own worktree and PR — never parked as an unticked task.
- The wiring-guard double check: a `test:` recipe that drops a file must keep that file under SOME
  gate CI calls, or the assertion is gone, not moved. Verify the file is still named by
  `test-unit`/`test-install-ci`/`ci-install` after the move.
