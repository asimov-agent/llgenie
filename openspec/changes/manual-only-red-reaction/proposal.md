# manual-only-red-reaction

## Why

Two CI workflows act automatically when a PR (or pipeline) turns red, without a human starting them:

- **`run-failure-reactor.yml`** triggers on `workflow_run: [completed]` over the repo's own workflows
  and — on a failed run with no pushable PR — files a NEW issue on the board (issue #2076).
- **`fix-bot.yml`** auto-runs on its own `schedule` (`17 * * * *`) and on `workflow_run: [completed]`,
  auto-repairing red PR branches.

Owner directive (2026-11-08, verbatim): *"i want to disable the ci pipeline issue bot fixer when a pr
turns red, disable that a new issue on that, should be manually started!"* — both auto-triggers should
be off so nothing files or fixes an issue on a red PR unless a human starts it. The defect is live: on
PR #2298 at 21:37Z the run-failure-reactor (workflow_run) posted `bot-claim:` then
`bot-done: repair-unavailable` with `HTTP 403 — missing scope: workflow (classic PAT) or Actions:
write (fine-grained PAT)` — it claims PRs it cannot repair, for four hours, on every red PR.

## What changes

1. `run-failure-reactor.yml`: the `workflow_run: [completed]` trigger and its 32-name roster are
   REMOVED; `on:` becomes `workflow_dispatch` with a `run_id` input (needed so a human can still start
   it by hand). Its `gh issue create` arm runs only on a human dispatch. As a dispatchable workflow it
   now carries the shared owner/collaborator guard (issue #295).
2. `fix-bot.yml`: the `schedule: "17 * * * *"` AND `workflow_run: [completed]` triggers are REMOVED;
   the existing `workflow_dispatch` path stays.
3. Enforcement (negative control): a new `check-manual-only` rule in `scripts/check_workflows.py` makes
   `make check-workflows` FAIL if either file re-gains any non-`workflow_dispatch` trigger.
4. The reactor's dropped roster leaves 28 workflows whose reds are no longer auto-routed; each is given
   a dated entry in `tests/fixtures/workflow-run-exemptions.json` (a red is surfaced to a human now).
5. Stale tests (fix-bot's `workflow_run`/schedule pins, the removed sweep job's consumers,
   `fix-bot-resolve`, the dispatch-forms table) are updated to assert the dispatch-only wiring, and
   `docs/BOTS.md` re-states that both workflows are manual-only.

## Change-first

Issue #2293 is the surviving tracker. `make check-workflows` and `make check-wiring` are green with
quoted exit codes; the negative control (re-add a `schedule`/`workflow_run` trigger to either file)
reds the gate and restoring clears it. Base: `origin/main@aef9ee7b`. Branch:
`fix/2293-manual-only-react-fixbot`.
