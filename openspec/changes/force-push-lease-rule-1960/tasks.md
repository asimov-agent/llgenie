# Tasks

- [x] 1. `agents/standing-rules.md` carries the reworded rule. Verified: the diff hunk on PR #2449 (this branch)
- [x] 2. All 16 lane copies (`SOUL.md` ×13, pr-rebase reference, planner SOUL) carry the identical sentence. Verified: the file roster in the PR #2449 diff (18 files, 61 insertions)
- [x] 3. Change-note trio present: `agent-wiki/2026-11-09-force-push-rule-1960.md` + `docs/changes.d` fragment + `CHANGES.md` index row. Verified: `make check-docs` ran in CI `scope` at this head; trailing-newline lint clean after the sweep amend
- [x] 4. `make lint` green at this head. Verified: `make lint` OK locally at 666e82d33; CI lint job completed:success in run 42774977919
