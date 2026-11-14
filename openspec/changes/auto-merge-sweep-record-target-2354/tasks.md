# Tasks: auto-merge-sweep-record-target-2354

- [x] Rewrite step 5 of `agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md` to name
      exactly one target: rolling record tracker #2652, fixed first line, per-PR deferral reasons;
      no tick-card id, no closed-#2101 fallback.
- [x] File the rolling record tracker issue #2652 (never-closes) and the fleet-outage side issue
      #2653 for the emptied planner jobs.json / lost orchestrator-tick job.
- [x] Restore the planner `cron/jobs.json` live jobs `db0a3e1a3d7c` (new prompt) and
      `71c5192ebdba` (committed prompt), 30m cadence, byte-identical to the committed copies.
- [x] Replay `make check-cron-drift` on the host: both jobs OK, exit 0.
- [x] Run one real sweep (`make auto-merge-recheck REPO=asimov-agent/llgenie MAX=50`) and record it
      on #2652 in the fixed format; quote the comment id.
- [x] Replay the dead-card greps: `git grep -n 'Record on the tick card' -- agents/` rc=1 (no
      live record procedure names the dead card; surviving `cc5d2bd4083a` hits name the tick
      CRON-JOB id in the gates/contracts driving it + dated records) and
      `gh issue view 2652 --json state` (OPEN).
- [x] Change-note trio + wiki entry land in the lane commit and the commit message carries the
      ticked AC mirror (proven: `git show --name-only HEAD | grep sweeper-record-target-2354` names
      agent-wiki + changes.d + the openspec change; `git log -1 --format=%B | grep -c '^- \[x\]'`
      = 3).
