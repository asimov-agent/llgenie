# Tasks: agents-md-task-pacing

- [x] 1. File the GitHub issue carrying the goal (#2956); fold the approved #2527 bullet into the same lane
- [x] 2. Create the feature branch worktree off the latest `origin/main` (f71e48e25153)
- [x] 3. Create the OpenSpec change via the CLI (`make openspec-new`)
- [x] 4. Write proposal.md + specs/host-task-pacing/spec.md
- [x] 5. Add the "Host-side task pacing (MANDATORY, durable)" section to `AGENTS.md` (owner-approved protected-file edit) (proven: owner chat approval 2026-11-20; `git diff` shows the section at head)
- [x] 6. Add the #2526 start-surface gate bullet to AGENTS.md §"Every workflow file is validated" (owner-approved protected-file edit) (proven: owner chat approval 2026-11-20; bullet names R1/R2/R3 + zero-exemption fleet)
- [x] 7. Add the agent-wiki entry + `docs/changes.d/` fragment and run `make changes-index` (proven: `make changes-index` rc=0, 922 fragments rendered)
- [x] 8. `make check-docs` and `make lint` green on the branch (proven: `make check-docs` rc=0; `make lint` rc=0 LINT OK)
- [x] 9. `make openspec-validate NAME=agents-md-task-pacing` exits 0 (proven: "Change 'agents-md-task-pacing' is valid")
- [x] 10. The commit text carries the closing wiring for both issues and the mirrored ticked acceptance block (`git log -1` shows `closes #2956` and `closes #2527` as separate lines and four `- [x]` acceptance items)
