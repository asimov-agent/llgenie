# worktree-prune-leftover — Tasks

Issue: [#759](https://github.com/asimov-agent/llgenie/issues/759)

- [x] 1. `apply()` reports a worktree it could not fully delete as a leftover: path, reason and the one command that clears it.
- [x] 2. `apply()` clears root-owned debris through the container engine as root, then retries `git worktree remove` once.
- [x] 3. A leftover is not an error: `main()` exits 0 when every planned action happened or was reported as keep/leftover with its reason.
- [x] 4. `render()` prints one leftover line per undeletable directory and keeps the summary counts honest.
- [x] 5. `tests/test_worktree_prune.py` drives the real `apply()` against a worktree holding an undeletable file and asserts the leftover report and exit 0.
- [x] 6. `tests/test_worktree_prune.py` covers the container-engine path with a stubbed runtime on `PATH`.
- [x] 7. `make test-unit` and `make check-wiring` pass; `make openspec-validate NAME=worktree-prune-leftover` exits 0.
