# CI-fail read-the-failing-job — tasks

- [x] write `agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`
      (mandatory red-bot-gate sequence, verbatim log-read commands, gate→defect map, green-report
      discipline, unretrievable-log rule)
- [x] add the reference pointer to `containerized-repo-verification/SKILL.md`
- [x] openspec change dir (`proposal.md`, `spec.md`, `tasks.md`, `.openspec.yaml`)
- [x] change-note trio: `agent-wiki/2026-11-06-ci-fail-read-the-failing-job.md` + `docs/changes.d/2026-11-06-ci-fail-read-the-failing-job.md` fragment + `CHANGES.md` row (#1123)
- [x] validate: `make openspec-validate NAME=ci-fail-read-the-failing-job`, `make openspec-tasks-check`, `make check-docs`, `make lint`
- [x] PR body carries `AGENTS:`/`BASE:` + `closes #1791`, ready-for-review, not draft
