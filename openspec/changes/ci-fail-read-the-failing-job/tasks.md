# CI-fail read-the-failing-job — tasks

- [x] write `agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`
      (mandatory red-bot-gate sequence, verbatim log-read commands, gate→defect map, green-report
      discipline, unretrievable-log rule)
- [x] add the reference pointer to `containerized-repo-verification/SKILL.md`
- [x] openspec change dir (`proposal.md`, `spec.md`, `tasks.md`, `.openspec.yaml`)
- [x] change-note trio: `agent-wiki/2026-11-06-ci-fail-read-the-failing-job.md` + `docs/changes.d/2026-11-06-ci-fail-read-the-failing-job.md` fragment + `CHANGES.md` row (#1123), reconciled to name the #1792 AC-self-red (reviewer-owned) in the gate→defect map alongside the reference and spec
- [x] validate: `make openspec-validate NAME=ci-fail-read-the-failing-job`, `make openspec-tasks-check`, `make check-docs`, `make lint`, `check_pr_hygiene.py agents-line`, `check_pr_hygiene.py sync-line`, `check_pr_hygiene.py openspec-change`
- [x] #1724: re-sync the live profile (`make sync-agent-profile PROFILE=llgenie-issse-implementer` → 7 files byte-identical) and report the `SYNC:` line in the PR body
- [x] independent verification: fresh standalone clone of `fix/1791-ci-fail-read-the-failing-job` → HEAD `e3bd7f06` == pushed sha, all delivered artifacts byte-present, check-docs OK there
- [x] PR body carries `AGENTS:`/`BASE:` + `closes #1791` + the issue's acceptance criteria, ready-for-review, not draft
