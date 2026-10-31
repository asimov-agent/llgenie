# Version the planner's grown orchestration reference into the tree (issue #1224)

The planner lane's versioned tree under `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/`
lacked a reference grown this session: **`already-resolved-vs-live-slice.md`** (live 5,655 b). It
captures, grounded in this session's verified evidence, the discipline that a lane claiming
"already resolved on main" must:

1. verify on the API, not argue — hermetic-twin / `@network`-wrapper shape for live-data drift;
2. a fresh PR born before the latest merge can be base one merge stale and read as a mass-revert —
   verify `git merge-base origin/main <head>` + `git show <head>:<file>` for files merged by the
   newest PR (#1219/#1220 on `6d990570` vs `d98c569c`);
3. a rebase that drops the mass-revert is the only cure; "green local" is never the gate;
4. a shared broken gate (e.g. census pointer not an ancestor of main, #1221) blocks every PR's
   `scope` — file one root fix, route to the gate's owner, clear each lane's own diff;
5. lane PR-identity reports are claims — resolve via branch→PR lookup, never the cited number
   (engine-improver's #1218/#1219-vs-#1220 drift).

Committed byte-identical to the planner's live profile (profile versioning per #791/#1062); the
paired `docs/changes.d/` row + `CHANGES.md` index satisfy the change-note gate (#1123). No merge —
owner approval, implementer only commits the text.
