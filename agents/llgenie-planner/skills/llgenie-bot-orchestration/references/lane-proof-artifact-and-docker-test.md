# Reading a lane's own proof artifact, and running one test file in the canonical container

## An "honest read-channel blocker" is often already resolved on disk — read the proof yourself

When a lane reports its read channel (terminal / read_file / search_files) is down mid-session
but write_file, docker and `gh api` still work, it will refuse to *claim* green without being able
to prove the test run. That refusal is correct — but the proof it could not read is usually already
sitting in the worktree: a marker the lane's own docker/pytest step wrote (typically a small `*.txt`
at the worktree root holding the pytest tail and an `RC=0` line). Glob the worktree root and `cat`
it from your working read channel before treating the blocker as parked.

- If the marker names the pass count and `RC=0`, the lane is done: hand it the confirmation **and**
the evidence path so it stops re-proving blind and proceeds to open its PR.
- Do **not** re-run the whole suite to "double-confirm" — the on-disk marker is the artifact; a
  read/test loop to reproduce it burns turns and (see below) can trip the progress guard.
- Verify the marker is not stale: match its claim (test count, file names) against the branch head
  and the current test file's size. A marker written before the last edit proves the old tree.

Hold the lane boundary while doing this: a planner who verifies evidence must not slip into
implementing the fix. If a progress guard halts your read-only probes, that is the signal to drain
the verified evidence into a DM and stop — not to start mutating the worktree.

## Running one test file through the canonical container

The llgenie test image is `llgenie/test:latest` (`Makefile: TEST_IMG := llgenie/test:latest`), **not**
`base-cpu:test` (that image has no python). `make test-unit` is
`docker run $(TEST_OPTS) $(TEST_IMG) python scripts/unit_tests.py run`; to run a single file, mirror
`TEST_OPTS` (`--rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root`) and pass the command
explicitly:

```
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/test_X.py -p no:cacheprovider -q
```

Wrapping the command in `sh -c '...'` or overriding `--entrypoint python` fights the image (its
ENTRYPOINT is empty, `CMD=/bin/sh`) and yields `python: not found`. The command belongs on the
docker CLI as trailing args, not inside a shell wrapper.
