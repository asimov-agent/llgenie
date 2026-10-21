# Tasks — hermes-smoke-tool-call (issue #407)

- [x] 1. OpenSpec change: `proposal.md`, `specs/hermes-smoke-tool-call/spec.md`, this checklist
- [x] 2. `scripts/hermes_smoke.py`: the nonce file, the prompt, the Hermes run, the transcript read from `$HERMES_HOME/state.db`, and the named failures
- [x] 3. `Makefile`: `nous-model` as the one place the alias name lives; `_hermes-smoke` runs `scripts/hermes_smoke.py run`; `hermes-smoke`'s `##` help line states the tool-call contract
- [x] 4. `tests/test_hermes_smoke.py`: the prompt lock, the four transcript verdicts, the missing-transcript failures, and the wiring (script invoked by `_hermes-smoke`, `issue-bot.yml` runs `make hermes-smoke`, the old text-echo prompt gone); `tests/test_issue_implementer.py` and `tests/test_scrub_log.py` updated for the new single source and the script leg
- [x] 5. `README.md` names the smoke's contract, and `agent-wiki/2026-10-21-hermes-smoke-tool-call.md` records the change with #407 and the PR
- [x] 6. Verified: `make test-unit` green, `make check-docs` green, `make openspec-validate NAME=hermes-smoke-tool-call` green, and a live `make hermes-smoke` that fails on a text-only transcript and passes on a real terminal call
