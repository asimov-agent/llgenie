# salvage-four-bucket degrades when gh is absent

## Why

`salvage-four-bucket.py` calls `gh pr list` through its `run()` helper, which caught only
`subprocess.SubprocessError`. A command absent from PATH (gh is not shipped in the unit-test
container) raises `FileNotFoundError` — an `OSError`, NOT a `SubprocessError` — so the guard let
it traceback instead of returning the "failed call" answer. Measured on a clean detached worktree
of `61155e9a` (2026-11-13): running the audit in the gh-less test image prints a raw traceback
ending `FileNotFoundError: [Errno 2] No such file or directory: 'gh'`.

That reddens the local unit battery on any dirty multi-worktree host — via
`test_every_python_script_is_executable_and_prints_usage_without_args`, exactly the crash mode it
asserts against — while CI stays green because GitHub runners ship gh. The defect is enforced
nowhere it is caught, and loud only where verification happens.

## What Changes

- **`run()`** in `salvage-four-bucket.py` now catches `(subprocess.SubprocessError, OSError)` and
  returns `None`, so a missing executable reads like any other failed call and `out()` returns
  `""` — the audit no longer dies, it degrades.
- When `shutil.which("gh")` is `None`, `main()` prints a **degraded note** to stderr that PR
  identity could not be checked, and still classifies branches by merge-base alone.
- A **regression test** drives the audit's classification leg in a real gh-less fixture repo and
  asserts rc=0, no traceback, the degraded note, and that the orphan branch is still classed.

## Acceptance

- The audit run with no arguments in the gh-less test container on a dirty multi-worktree host
  exits rc=0 with no traceback.
- `tests/test_rebase_lane_scripts.py::test_the_audit_degrades_when_gh_is_absent` FAILS on the
  pre-fix code (FileNotFoundError) and PASSES on the fixed code.
- `make test-unit` green; `make openspec-validate NAME=salvage-four-bucket-gh-absent` exits 0.
