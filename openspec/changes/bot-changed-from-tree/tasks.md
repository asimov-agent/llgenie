# Tasks — bot-changed-from-tree (issue #428)

- [ ] 1. OpenSpec change: `proposal.md`, `specs/bot-changed-from-tree/spec.md`, this checklist
- [ ] 2. `scripts/issue_implementer.py`: `changed` (the tree, run inputs excluded) + the `changed` subcommand, exit 2 when git cannot read the tree
- [ ] 3. `Makefile`: `issue-bot-changed` target, `.PHONY`, `##` help line
- [ ] 4. `.github/workflows/issue-bot.yml`: a detect step, the push gated on `changed`, the loud failure covering `rc != 0` or no change, no `implemented` from an exit code
- [ ] 5. `tests/test_issue_implementer.py`: real-git cases for no change / a real edit / an unreadable tree, and the workflow gating check
- [ ] 6. `README.md` + `agent-wiki/2026-10-21-bot-changed-from-tree.md` record the target and what it measures
- [ ] 7. Verified: `make test-unit` green, `make check-docs`, `make lint`, `make check-wiring`, `make openspec-validate NAME=bot-changed-from-tree` green, and `make issue-bot-changed` shown on a tree that only wrote `triage.md`
