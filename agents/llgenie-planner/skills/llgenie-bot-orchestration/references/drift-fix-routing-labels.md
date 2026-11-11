# Drift-fix routing labels

**Drift/verify issues move only when they carry the routing label — a DM dispatch alone leaves them label-less and off the implement queue.** (owner 2026-11-04, #1712/#1713 class)

A `verify: <gate> red on main` issue that a lane owns stays invisible to the fleet — CI bots select on labels, and the owner board reads labels. Posting a dispatch comment or DMing the lane is necessary but NOT sufficient: the board still shows the issue un-labeled, so the lane sees it, but no clean-up/implement bot picks it and the owner can't see routing at a glance.

- After dispatching a drift fix to a lane, apply `continuous-improvement` (recurring pipeline-health defect) + `agent:implement` (PR-worthy failure a bot picks up) so the issue joins the implement queue and the board shows ownership.
- Verify with `gh api repos/asimov-agent/llgenie/issues/<n> --jq .labels` — read back the applied set, don't trust the POST alone.
- Only add labels whose meaning matches: `continuous-improvement` for recurring pipeline-health, `agent:implement` for a PR-worthy fixable defect. `do-not-merge` is a hold with a tracked removal condition — never add it to force-route.
- A label change is an owned planner mutation: cheap, reversible, board-visible. Making it (and reading it back) beats another DM that consumes a lane cycle without changing the ownership surface.

**Verify fix DIRECTION before a branch becomes a PR (#1712 class, 2026-11-04).** A drift red can be re-classified (hermetic check green + generator emits carry-over NOTE = gate-logic flaw, in short), yet a lane owning the older data-books diagnosis can still open a wholesale data-refresh branch. Intercept it: `git fetch origin <branch>; git diff --name-only <merge-base> <branch>` — if it touches ONLY data/fixtures and NO scripts/Makefile, it cannot fix a gate seam and lands the wrong story. Also compare a sentinel plan's occurrence count (a regeneration shows 0→N, not a targeted carry-over). Direction is gate-logic vs data; verify which before the branch is reviewable.
