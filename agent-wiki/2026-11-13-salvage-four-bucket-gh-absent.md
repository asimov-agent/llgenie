# salvage-four-bucket.py degrades when gh is absent, never tracebacks

Issue: #2638. PR: opened by the issue-bot pipeline from this change's pr-body.md.

## What was wrong

`salvage-four-bucket.py` calls `gh pr list` through its `run()` helper, which caught only
`subprocess.SubprocessError`. A command absent from PATH — gh is not shipped in the unit-test
container — raises `FileNotFoundError`, an `OSError` that the guard did not catch, so the call
tracebacked instead of returning the "failed call" answer. Measured 2026-11-13 on a clean
detached worktree of `61155e9a`: running the audit in the gh-less test image printed a raw
traceback ending `FileNotFoundError: [Errno 2] No such file or directory: 'gh'`.

That reddened the local unit battery on any dirty multi-worktree host (via
`test_every_python_script_is_executable_and_prints_usage_without_args`) while CI stayed green
because GitHub runners ship gh — enforced nowhere it is caught, loud only where verification
happens.

## The fix

`salvage-four-bucket.py`:

- `run()` now catches `(subprocess.SubprocessError, OSError)` and returns `None`, so a missing
  executable reads like any other failed call and `out()` returns `""` — the classification leg
  no longer dies, it degrades.
- When `shutil.which("gh")` is `None`, `main()` prints a degraded note to stderr that PR
  identity could not be checked, and still classifies branches by merge-base alone.

`tests/test_rebase_lane_scripts.py::test_the_audit_degrades_when_gh_is_absent` drives the
audit's classification leg in a real gh-less fixture repo (git init/commit/push into a throwaway
bare remote, an orphan branch adding a path main lacks, and a PATH whose directory holding the
real gh is dropped with git re-staged into a scratch bin) and asserts rc=0, no traceback, the
degraded note, and that the orphan branch is still classed.

## Verified

- Focused battery: `pytest tests/test_rebase_lane_scripts.py` → 27 passed, rc=0.
- The new test FAILS on the pre-fix code (rc=1, `FileNotFoundError: [Errno 2] No such file or
  directory: 'gh'`) and PASSES on the fixed code — it is a real regression test, not a loosened
  assertion.
- gh-present run on this host: rc=0, no degraded note (the note fires only when gh is absent).
- `make lint` (trailing newlines) and `make openspec-tasks-check` pass. `make openspec-validate`
  is the CI gate and runs in the dockerized openspec container, which is unavailable in this
  agent container; the change files match the validated
  `openspec/changes/sync-agent-profile-tracked` structure.

## Current status

Change is implemented, uncommitted in `/repo`; `pr-body.md` is written for the job to open the
PR that closes #2638.
