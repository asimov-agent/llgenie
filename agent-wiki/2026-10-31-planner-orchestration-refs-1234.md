# Planner orchestration refs caught up to live, live→tree (issue #1234)

The planner lane's versioned tree under `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/`
lagged the live profile on six orchestration references grown this session. Measured on a fresh
`origin/main` (`45a04c3c`): `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` would not report
byte-identity until the tree carried the current live bytes. All six are now committed byte-identical
to the live profile, direction live→tree (live is richer, so the sync cannot truncate anything):

- **`agent-behaviour-versioning.md`** — live 10,125 b (tree was 9,782 b).
- **`change-note-gate.md`** — live 2,590 b (tree was 2,018 b).
- **`ci-gate-vs-live-pipeline.md`** — live 9,020 b (tree was 7,246 b).
- **`completion-gate-and-test-run.md`** — live 5,700 b (tree was 2,499 b).
- **`rebase-and-merge-mechanics.md`** — live 7,713 b (tree was 5,980 b).
- **`report-integrity.md`** — live 5,353 b (tree was 4,232 b).

This is profile versioning (#791, #1062) — the implementer lane commits the live text byte-identical;
it is not planner implementation and it is not merged by the implementer. Each of the six files was
verified byte-identical to `/home/asimov/.hermes/profiles/llgenie-planner/` (`cmp` at branch time and
re-verified at the final head); the paired `docs/changes.d/` row satisfies the change-note gate (#1123).
The sibling reference `verifying-lane-claims.md` is tracked separately by #1206/#1235, and
`already-resolved-vs-live-slice.md` by #1224.
