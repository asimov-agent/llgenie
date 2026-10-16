# A run-failure reactor: a red run becomes a fix or a deduped issue (#286)

Implemented by PR [#286](https://github.com/asimov-agent/llgenie/issues/286) (issue #286).

## Why

`fix-bot` (#222) is the only runtime failure handler and it is PR-shaped: it selects from
`gh pr list --state open` and filters on `gh pr checks`. Anything without an open same-repo PR is
invisible to it. No workflow in `.github/workflows/` carried a `workflow_run` trigger, so no bot
read a run's conclusion. A merge that broke `main` sat red until a human noticed; a failed weekly
`registry-sync`/`engine-bump` run posted no issue and no PR; a failed GHCR publish was silent.

## What landed

- **`scripts/run_failure_reactor.py`** (new, stdlib only, no LLM) — the route decision, never in a
  job `if:` (issue #107). **Route A**: a failed run with a pushable same-repo PR → claim the PR
  (`scripts/bot_claims.py`, issues #279/#285) and dispatch the **existing** `fix-bot`, reusing
  `scripts/fix_bot_sweep.py`'s eligibility rules (never duplicated). A **fork** PR is never
  dispatched (the token cannot push it). **Route B**: no pushable PR → file exactly ONE issue
  whose title names the workflow + failing job, whose body carries the failing job, its step, and
  a tail of `gh run view --log-failed`, deduped by the marker
  `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (searched `in:body`), labelled `agent:implement` so
  the issue-bot picks it up. It never repairs/commits/pushes/merges in Route B — it files.
- **`make run-failure-reactor`** (REPO=; RUN_ID=; DRY=1 previews) + `.PHONY` + `make help` +
  README.
- **`.github/workflows/run-failure-reactor.yml`** — `on: workflow_run: types: [completed]` over the
  repo's own workflows, guard-free (it is not dispatchable by hand, so issue #295's guard does not
  apply), carrying the owner PAT so the fix-bot dispatch carries the owner identity. The reactor
  skips its own workflow's completion to avoid re-triggering itself.
- **`tests/test_run_failure_reactor.py`** (new, in `make test-unit`) — fake `gh` on PATH, real
  script, real argv asserted. 9 cases: red main → one issue, same head sha → nothing (dedupe),
  same-repo PR → dispatch, fork PR → no dispatch, occupied PR → left alone, crashed decision →
  loud, file-path writes only an issue, and the workflow calls the reactor through a make target.

## Verification

- `tests/test_run_failure_reactor.py`: **9 passed** in `llgenie/test:latest`.
- `make openspec-validate NAME=run-failure-reactor`, `make lint`, `make check-wiring`,
  `make check-workflows`, `make check-dispatch-forms`, `make check-docs`, `make check-pr-hygiene`,
  `make openspec-tasks-check`.
- `make loop` GREEN (LOOP_EXIT=0, every stage passes).

## Note

The reactor composes the existing bots; it does not duplicate their logic (one path per resource,
AGENTS.md). The issue-bot owns implementation, the fix-bot owns PR repair. A run it cannot diagnose
is reported loudly, never silently dropped.
