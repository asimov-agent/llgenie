# Tasks

- [x] 1. `issue-refiner.yml`: claim/pick, apply and report steps use `github.token` (the job declares `issues: write`)
- [x] 2. `issue-bot.yml`: the verdict step uses `github.token`; the push step keeps the owner PAT
- [x] 3. `fix-bot.yml`: the sweep's `gh workflow run` uses `github.token` (its job declares `actions: write`)
- [x] 4. `run-failure-reactor.yml` + `queued-alarm.yml`: the issue/dispatch writes use `github.token`
- [x] 5. `tests/test_bot_write_tokens.py`: locks the token per writing step, the permission per job, and the PAT on every pushing job (and fails on the old wiring)
- [x] 6. `README.md` documents which token makes which write; `agent-wiki/2026-10-20-bot-write-credential.md` records the work with issue #412 and the PR
- [x] 7. Verification: a real `workflow_dispatch` of `issue-refiner` and of `fix-bot` on this branch, the refiner's claim comment landing, `make check-workflows`, `make check-dispatch-forms`, `make lint`, `make openspec-validate NAME=bot-write-credential`, `make test-unit`
