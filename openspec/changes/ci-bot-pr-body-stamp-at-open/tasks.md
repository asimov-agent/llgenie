# Tasks

- [x] `scripts/bot_preflight.py`: `stamp_body(text, record)` inserts or replaces the pair, flush-left, adjacent, idempotent.
- [x] `scripts/bot_preflight.py`: `resolve_record(root, base, refs)` measures from the first resolvable ref and refuses otherwise.
- [x] `make bot-stamp-body BODY= [OUT=] [BASE=] [REFS=]` with its `## help` line, usage guard and `.PHONY:` entry.
- [x] `issue_implementer.render_pr_body` requires the record and stamps; `open_pr` resolves it and refuses when it cannot.
- [x] `engine-bump.yml` and `registry-sync.yml` stamp the body file before `gh pr create` / `gh pr edit`.
- [x] `security_bot.pr_body` / `security_bumps.pr_body` stamp from a record resolved before any git mutation.
- [x] `fix-bot.yml` re-stamps a synced repair and its outcome comment reads `steps.push.outputs.pushed`.
- [x] `tests/test_bot_stamp_body.py`: stamp, idempotence, gate-accept/negative-control, refusal, producer wiring, false-push claim.
- [x] The two security fixtures provision a real `main` + `origin/main` so the stamp is measured, not stubbed.
- [x] `docs/BOTS.md` documents `make bot-stamp-body` and records the #2050 finding.
- [x] `agent-wiki/2026-11-08-bot-pr-body-stamp-at-open.md` + `CHANGES.md` index row.
- [x] `make openspec-validate NAME=ci-bot-pr-body-stamp-at-open` exits 0.
