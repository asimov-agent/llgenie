# engine-bump-rebase-ci

## Shared sync module

- [x] 1.1 Create `scripts/engine_bump_sync.py` with `is_engine_bump_pr`,
      `upstream_remote`, `upstream_main`, and `sync_pr_with_main` (the pure
      forward-merge logic, parameterized by `repo`/`run_git`/`log`).
- [x] 1.2 `sync_pr_with_main` returns True only on a clean merge; a conflict
      aborts and returns False (never force-pushes).

## Dispatcher reuse

- [x] 2.1 Refactor `scripts/watchloop_dispatch.py` to import the four functions
      from `engine_bump_sync` (delete the local copies).

## CI entrypoint + workflow

- [x] 3.1 Create `scripts/engine_bump_rebase.py`: list open `chore/engine-bump-*`
      PRs via the GitHub API, call the shared `sync_pr_with_main` for each behind
      one; `--dry` prints without pushing.
- [x] 3.2 Create `.github/workflows/engine-bump-rebase.yml`: daily cron +
      `workflow_dispatch`, checkout `main` with `secrets.BUMP_TOKEN`, run the
      entrypoint, guarded like `engine-bump.yml`.

## Tests

- [x] 4.1 `tests/test_engine_bump_sync.py` — classification, remote resolution,
      clean-merge sync, conflict returns False.
- [x] 4.2 `tests/test_engine_bump_rebase.py` — dry-run reports without pushing;
      behind PR is rebased; workflow YAML contains cron + BUMP_TOKEN + entrypoint.
- [x] 4.3 `tests/test_watchloop_dispatch.py` — dispatcher uses the shared module.

## Verification

- [x] 5.1 `make openspec-validate NAME=engine-bump-rebase-ci` exit 0.
- [x] 5.2 `make test-unit` green (new sync/rebase tests + existing dispatcher
      tests still pass).
- [x] 5.3 `make lint` clean.
- [x] 5.4 Pushed to the feature branch; PR opened against `main` referencing the
      issue; issue + PR bodies aligned.
