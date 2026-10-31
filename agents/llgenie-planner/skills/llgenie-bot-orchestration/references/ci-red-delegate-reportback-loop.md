# The CI-red → delegate → report-back → SOUL-update → re-sync loop (owner standing rule, 2026-10-30)

Owner standing behaviour (plain):

1. **Monitor the CI pipelines** (every pass, every tick — `gh run list` + per-PR check-runs at the head, not just job names).
2. **If a pipeline is red**, **delegate a task to the relevant llgenie bot** — name the issue/run, the failing check, the head sha, what "fixed" means, one lane.
3. **That bot reports back to the planner** on the task outcome (id, branch, head, run id, evidence) per #1010 — a report without evidence is a mood.
4. **Tell the bot to update its SOUL/skill behaviour** based on what it learned in this task, so the lesson is versioned, not session-only.
5. **Based on what it reports, sync and re-report** to the owner until the reported issue is completed (green). Keep the loop running; never stop at "waiting".
6. **The planner ALSO updates its own skill/SOUL** from what the loop teaches, and **tells the lanes to re-update theirs** to match — behaviour is versioned both ways.

Concretely: the fleet is in a reporting→sync→re-dispatch cycle until the red run turns green. Each skill/SOUL edit is a tracked change (the owned repo path) — a SOUL write is protected when it's a lane's live agent-instruction file; version it via issue+PR (#791/#1030), not a workaround edit. But a bot's OWN skill reference under this profile is its own to update via skill_manage.

Close the loop with evidence: quote the completed green run / merged PR / passed check at the resolved head, then note the planning-level lesson and the lane's SOUL-update. This is the standing operating behaviour, not a one-off.
