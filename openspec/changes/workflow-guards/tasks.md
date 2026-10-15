# Tasks

- [x] 1. One guard body (`.permission` for actor + triggering_actor, `admin|maintain|write`, refusal as a non-zero exit) replaces the weaker forms in `ci.yml`, `engine-bump.yml`, `engine-bump-rebase.yml`, `registry-sync.yml` and `fix-bot.yml`'s step guard
- [x] 2. `queued-alarm.yml` gains the guard job and `alarm` needs it (it was the only dispatchable workflow without one)
- [x] 3. `ci.yml`'s declared-but-unread `allowed` output is removed, with the refusal mechanism stated in the comment
- [x] 4. The step is byte-identical in all eleven guard sites: the six near-copies (`code-review-bot`, `fix-bot`, `issue-bot`, `issue-refiner`, `publish-agent-image`, `rebase-bot`) normalize to the same `name:`/`env:`/`run:` (each guard authenticates with the run's own `github.token`, never the job-level `BUMP_TOKEN` PAT)
- [x] 5. `tests/test_workflow_guards.py` (in `make test-unit`): guard present, write-level, both actors, actually gating, no dead guard output — the last rule over EVERY workflow — and one byte-identical body
- [x] 6. Falsified: the new tests fail on the pre-fix workflows (`5 failed, 1 passed`) and on a drifted guard body (the byte-identity case), and pass on this branch (`6 passed`)
- [x] 7. The two tests that pinned the removed `curl` + `Authorization` guard shape (`test_engine_bump_rebase.py::TestWorkflowYaml::test_guard_sends_the_default_token_variable`, `test_engine_bump.py::test_guard_keeps_default_token`) now assert the `gh api` + default-token shape — they were the only red jobs on the first PR run
- [x] 8. README has a "who may start a bot or publish" section; `agent-wiki/2026-10-15-workflow-guards.md` records the audit; `make lint`/`check-docs`/`check-wiring`/`check-dispatch-forms`/`openspec-validate` exit 0
