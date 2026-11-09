# Tasks

- [x] 1. `openspec/changes/stall-reclaim-log-axis` — proposal + `specs/stall-reclaim/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before the code
- [x] 2. `agents/llgenie-planner/scripts/stall_reclaim.py` — Python port: lane `agent.log` mtime + `API call #N` delta over two samples ≥ 60 s apart (never the per-run kanban log); `classify()` matrix; two-consecutive-STALLED gate; both-samples operand printing
- [x] 3. `agents/llgenie-planner/scripts/stall_reclaim.py` — allowlist, churn cap, kanban-path-only-via-`reclaim`/`block` (no signal), separate DM reaper function, `tasks:`/`dm:` summary lines, DRY leaves no state file
- [x] 4. `tests/test_stall_reclaim.py` — threshold matrix, advancing-log regression pin, stale worker STALLED, two-consecutive-verdicts, churn cap, allowlist, no-kill-in-kanban-path / task_runs-pid-never-reaches-DM, negative control, operands in verdict line
- [ ] 5. Run `python3 -m pytest tests/test_stall_reclaim.py -q` locally (all pass) + `make unit`, `make lint`, `make check-docs`
- [ ] 6. `make openspec-validate NAME=stall-reclaim-log-axis` passes; agent-wiki note + docs/changes.d row + `CHANGES.md` regenerated; push; open the upstream PR (no auto-merge, no merge)
