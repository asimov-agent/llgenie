# CI-fail failing-job-log pointer — tasks

- [x] 1. write `agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/read-the-failing-job-log-pointer.md` naming the canonical implementer reference (merged via #1840) and the engine-improver context for the read-the-failing-job-log-first sequence
- [x] 2. add the pointer row to the lane skill's `SKILL.md` proving/references section (skill-surface pointer per #1791-AC3)
- [x] 3. openspec change dir (`proposal.md`, `spec.md`, `tasks.md`, `.openspec.yaml`)
- [x] 4. change-note trio: `agent-wiki/2026-11-06-engine-improver-failing-job-log-pointer-1849.md` + `docs/changes.d/2026-11-06-engine-improver-failing-job-log-pointer-1849.md` fragment + `CHANGES.md` row (#1123)
- [x] 5. validate: `make openspec-validate NAME=ci-fail-failing-job-log-read-pointer`, `make openspec-tasks-check`, `make changes-index`, `make check-docs`, `make lint`, `make skills-validate`, `check_pr_hygiene.py agents-line`, `check_pr_hygiene.py sync-line`, `check_pr_hygiene.py openspec-change`, `check_pr_closing.py check`
- [x] 6. #1724: content-add the pointer file + SKILL row to the live profile and report the `SYNC:` line in the PR body
- [x] 7. PR body carries `AGENTS:`/`BASE:`/`SYNC:` + issue reference, ready-for-review, not draft, canonical `asimov-agent` head
