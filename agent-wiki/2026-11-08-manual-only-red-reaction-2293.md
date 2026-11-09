# run-failure-reactor + fix-bot become manual-only (issue #2293) — 2026-11-08

**Implements:** issue #2293 — both red-PR automation workflows were auto-triggered on
`workflow_run:[completed]` (and fix-bot on its own hourly `schedule`), so a red PR auto-filed issues
and auto-repaired branches without a human starting anything. Owner directive (2026-11-08): *"disable
the ci pipeline issue bot fixer when a pr turns red ... should be manually started!"*. The defect was
live: on PR #2298 at 21:37Z the run-failure-reactor (a `workflow_run` reaction carrying no
`workflow_dispatch`) posted `bot-claim:` then `bot-done: repair-unavailable` with `HTTP 403 — missing
scope: workflow (classic PAT) or Actions: write (fine-grained PAT)` — it claims PRs it cannot repair,
for four hours, on every red PR.

## What changed

1. `run-failure-reactor.yml` — the `workflow_run:[completed]` trigger and its 32-name roster are gone;
   `on:` is now `workflow_dispatch` with a required `run_id` input (+ optional `context`), so the
   `gh issue create` arm runs only on a human dispatch. As a dispatchable workflow it gained the shared
   byte-identical owner/collaborator guard (issue #295). The reactor step reads `inputs.run_id`.
2. `fix-bot.yml` — the `schedule: "17 * * * *"` AND `workflow_run:[completed]` triggers are gone; the
   existing `workflow_dispatch` path stays, and the now-dead `sweep` job is removed.
3. **Enforcement (negative control)** — `scripts/check_workflows.py` gained `check-manual-only`: a
   re-added non-`workflow_dispatch` trigger in either file makes `make check-workflows` FAIL. Measured
   both directions: re-adding `schedule` or `workflow_run` reds the gate (`re-gained a non-dispatch
   trigger`), restoring clears it.
4. **Exemptions** — the reactor's dropped roster left 28 workflows whose reds are no longer auto-routed;
   each has a dated entry with a reason in `tests/fixtures/workflow-run-exemptions.json` (a red is
   surfaced to a human now).
5. Stale tests updated (fix-bot's `workflow_run`/schedule pins, the removed sweep job's `OWN_FORK` and
   `fix-bot-resolve` consumers, the dispatch-forms table) plus `docs/BOTS.md` re-states both as
   manual-only.

## Verification

`make check-workflows` rc=0, `make check-wiring` rc=0, `make check-dispatch-forms` rc=0,
`make check-docs` rc=0, `make lint` rc=0; the affected test modules (180 tests) pass in the test
container; the negative control reds and restores. `make openspec-validate
NAME=manual-only-red-reaction` exits 0.
