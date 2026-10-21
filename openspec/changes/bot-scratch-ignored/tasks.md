# Tasks — bot-scratch-ignored (issue #427)

- [ ] 1. OpenSpec change: `proposal.md`, `specs/bot-scratch-ignored/spec.md`, this checklist
- [ ] 2. `.gitignore`: `triage.md` joins the run inputs, and the comment says which leg writes what
- [ ] 3. `.github/workflows/issue-bot.yml`: the `git reset -q -- issue.md` denylist line is gone
- [ ] 4. `tests/test_bot_scratch_ignored.py`: real-git ignore checks for the roster, the roster/producer cross-check, the denylist guard, and a written `triage.md` not appearing as a change
- [ ] 5. `README.md` + `agent-wiki/2026-10-21-bot-scratch-ignored.md` record the run-input contract
- [ ] 6. Verified: `make test-unit` green, `make check-docs`, `make lint`, `make openspec-validate NAME=bot-scratch-ignored` green, and the real `git check-ignore` results shown
