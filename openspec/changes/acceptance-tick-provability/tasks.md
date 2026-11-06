# Tasks — acceptance-tick-provability

- [x] Extend `scripts/check_pr_acceptance.py` with a `tick-unprovable` finding: a ticked criterion
      whose `(proven: …)` names neither a CI `run=<id>` nor a reproducible `command rc=<n> <sha>`
      is red (fold/sync #1784/#1819 class; bare `- [x]` with no evidence = #745 self-tick).
- [x] Test the gate in `tests/test_check_pr_acceptance.py`: the #1784/#1819 fold-tick form reds,
      a sha-without-rc reds, a named `run=` green, a reproducible `command rc=<n> <sha>` green, and
      a bare tick with no evidence reds.
- [x] Add change-note pair (agent-wiki + docs/changes.d fragment + CHANGES.md row) documenting the
      #1784/#1819 class resolved.
- [x] Validate: `make openspec-validate NAME=acceptance-tick-provability`,
      `make openspec-tasks-check`, `make check-docs`, `make lint`.
- [x] PR body carries `## Acceptance criteria` `- [ ]` checklist + `closes #1858`.
