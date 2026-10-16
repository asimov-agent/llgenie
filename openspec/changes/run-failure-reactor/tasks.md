# Tasks

- [x] 1. `scripts/run_failure_reactor.py`: the stdlib-only route decision — Route A (pushable
      same-repo PR -> claim + dispatch the existing fix-bot, reusing `fix_bot_sweep`'s eligibility)
      and Route B (no pushable PR -> file ONE marker-deduped issue labelled `agent:implement`,
      carrying the failing job + log tail). Never repairs/commits/pushes/merges in Route B.
- [x] 2. The claim protocol (issues #279/#285): consult `bot_claims.occupied` before dispatching,
      claim the PR before the dispatch, use `PR_CLAIM_TTL` so readers honour the announced window.
- [x] 3. `make run-failure-reactor` + `.PHONY` + `make help` + README, so the target is reachable
      exactly as every other stage is.
- [x] 4. `.github/workflows/run-failure-reactor.yml`: `on: workflow_run: types: [completed]`,
      no guard (it is not dispatchable by hand, so issue #295's guard does not apply), carrying the
      owner PAT so the fix-bot dispatch carries the owner identity; the reactor skips its own
      workflow's completion to avoid re-triggering itself.
- [x] 5. `tests/test_run_failure_reactor.py` wired into `test-unit`; fake `gh` on PATH, real
      script, real argv asserted. Covers: red main -> one issue, same head sha -> nothing (dedupe),
      same-repo PR -> dispatch, fork PR -> no dispatch, occupied PR -> left alone, crashed decision
      -> loud.
- [x] 6. Verify: `make test-unit` (4691 passed), `make openspec-validate NAME=run-failure-reactor`,
      `make lint`, `make check-wiring`, `make check-workflows`, `make check-dispatch-forms`,
      `make check-docs`, `make check-pr-hygiene`, `make openspec-tasks-check`.
- [ ] 7. The full `make loop` gate is GREEN (LOOP_EXIT=0, every stage passes).
