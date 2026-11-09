# manual-only-red-reaction — tasks

- [x] `.github/workflows/run-failure-reactor.yml` — `workflow_run:[completed]` + 32-name roster removed; `on:` becomes `workflow_dispatch` with a required `run_id` input (+ optional `context`); the byte-identical owner/collaborator guard added (job `guard`, `react: needs: guard`); reactor step and Report read `inputs.run_id`; header rewritten manual-only
- [x] `.github/workflows/fix-bot.yml` — `schedule: "17 * * * *"` and `workflow_run:[completed]` removed; `workflow_dispatch` path kept; the now-dead `sweep` job removed; header rewritten manual-only
- [x] `scripts/check_workflows.py::check_manual_only` — a re-added non-`workflow_dispatch` trigger in either file is a `workflow-manual-only` violation (negative control, measured: re-add `schedule`/`workflow_run` → gate red, restore → green)
- [x] `tests/fixtures/workflow-run-exemptions.json` — the 28 workflows the reactor's dropped roster left uncovered each gain a dated entry with a reason (a red is surfaced to a human)
- [x] stale tests updated: `tests/test_workflows_valid.py` (manual-only pins), `tests/test_fix_bot_sweep.py` (no workflow_run/schedule pin; sweep-removed OWN_FORK), `tests/test_bot_write_tokens.py` (sweep dispatch entry gone), `tests/test_resolve_run_pr.py` (fix-bot no longer resolves a run), `tests/test_bot_pipeline_isolation.py` (fix-bot schedule dropped; reservation set survives via queued-alarm)
- [x] `docs/BOTS.md` — reactor + fix-bot re-stated manual-only; dispatch-forms table regenerated (reactor row added); cron slot table has no fix-bot row; odd-minute/roster prose updated
- [x] lane skill map `agent-wiki`… references: `pipeline-map.md` reactor + fix-bot rows updated to dispatch-only
- [x] guarded: `make check-workflows` rc=0, `make check-wiring` rc=0, `make check-dispatch-forms` rc=0, `make check-docs` rc=0, `make lint` rc=0; 180 affected tests green in the test container
- [x] negative control reported (both directions); change-note trio (agent-wiki + docs/changes.d + CHANGES.md via `make changes-index`)
