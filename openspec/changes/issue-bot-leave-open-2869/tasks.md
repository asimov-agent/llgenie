# Tasks — issue-bot-leave-open-2869

- [x] 1. `scripts/issue_implementer.py`: add the `hold` verdict to `VERDICTS`, the
      `TRIAGE: hold` shape to `DECISION_BLOCK`, and the close→hold guard in `apply_verdict`
      (`open_implementing_pr()` resolves every cited number through `gh api pulls/<n>`).
- [x] 2. Playbooks state the two close reasons and the leave-open rule:
      `.hermes/skills/issue-triage/SKILL.md`,
      `agents/llgenie-planner/skills/github-issue-triage/SKILL.md`,
      `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/references/planner-stale-state.md`.
- [x] 3. `scripts/bot_close_reasons.py` + `make bot-close-reasons-report` in `mk/bots.mk`
      (+ `.PHONY`, `scripts/package-layers.json` registration).
- [x] 4. Tests: extend `tests/test_issue_implementer.py` with hold-conversion + direct-hold +
      duplicate-still-closes tests; new `tests/test_bot_close_reasons.py` with the hermetic read
      and the three playbook-text assertions.
- [x] 5. Docs: `agent-wiki/2026-11-17-issue-bot-leave-open-2869.md` +
      `docs/changes.d/2026-11-17-issue-bot-leave-open-2869.md` (table-row).
- [x] 6. Live proof: targeted pytest rc=0; `make bot-close-reasons-report` at the head names
      #2048 with reason `completed`; file one side issue per issue the read flags
      `not_planned`-against-merged-PR (link both directions).
- [x] 7. `make test-unit` rc=0 on a clean tree at the head (3957 passed);
      `make openspec-validate NAME=issue-bot-leave-open-2869` rc=0.
- [x] 8. Commit + push `feat/issue-bot-leave-open-2869`, open the PR closing #2869 with the AC
      mirror and SYNC lines; confirm the gates are green and the PR is armed for auto-merge
      (never merged by hand).
