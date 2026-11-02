# Tasks — sweep-bot-dispatch (issue #1571)

## The guard carve-out

- [x] Add `EVENT: ${{ github.event_name }}` and `REF: ${{ github.ref }}` to every guard site
      (`.github/workflows/*.yml` `Owner / collaborator trigger guard` env).
- [x] Extend the bot allowance in the shared guard script: admit the bot when
      `EVENT == workflow_dispatch` (the repo's own dispatch path — a dispatch can only target this
      repo's own refs), keeping the existing same-repo-head allow and the owner/collaborator branch;
      all sites stay byte-identical (`make test-unit` passes `tests/test_workflow_guards.py`).
- [x] New guard execution tests: bot + `workflow_dispatch` (any of the repo's own refs) -> allowed;
      bot + non-dispatch event (no head) -> refused. Existing same-repo/foreign-head tests still pass.

## The sweep dispatches at its own ref

- [x] `.github/workflows/all-pipelines.yml` passes `REF="${{ github.ref_name }}"` so the sweep
      dispatches targets at the ref it is running from (the PR branch for a PR-head sweep, `main` for
      the weekly), so a pre-merge green sweep verifies the PR-branch guarded workflows.

## The sweep report names unverifiable workflows

- [x] `scripts/all_pipelines.py`: when a dispatched run concludes `failure` at its own trigger guard,
      render `NOT VERIFIED — refused at its own trigger guard` for that row (querying the run's jobs
      for a failed `guard` job with the rest skipped), instead of a bare `completed/failure`.
- [x] `tests/test_all_pipelines.py`: a guard-refused run renders `NOT VERIFIED — refused at its own
      trigger guard` and never a bare `completed/failure` cell; a genuinely-failed pipeline keeps
      `completed/failure`.

## Documentation

- [x] Update `docs/BOTS.md` guard paragraph + sweep paragraph (dispatch carve-out and dispatch-at-own-
      ref).
- [x] `make openspec-validate NAME=sweep-bot-dispatch` passes.

## Verification (issue acceptance criteria)

- [x] Dispatch `gh workflow run all-pipelines.yml` at the PR head and record the green sweep run id.
- [x] Confirm the sweep table names a workflow it could not verify with the reason (unit + live where
      reachable).
- [x] Confirm a foreign-head bot actor is still refused (negative control, guard execution test).
