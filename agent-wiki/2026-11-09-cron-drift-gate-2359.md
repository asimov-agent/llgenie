# The two new planner crons need a drift gate before they can stay versioned (issue #2359)

The planner now runs THREE recurring crons. Only the orchestrator-tick was versioned
(`agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`, gated by `check-tick-prompt`,
issue #2136). The two added this session existed only in the live
`~/.hermes/profiles/llgenie-planner/cron/jobs.json`:

- `db0a3e1a3d7c` **llgenie-auto-approve-merge** — runs `make auto-merge-recheck` (the #2101 retry),
  approves bot-authored green PRs, defers owner-authored (the #1088 identity constraint).
- `71c5192ebdba` **llgenie-auto-rebase-resolve** — measures DIRTY/CONFLICTING + BEHIND PRs and
  dispatches each to `llgenie-pr-merge-conflict`, excluding engine-chore.

A behaviour that lives only in one live profile evaporates on the next sync (#2084 class), and every
future planner re-creates it from scratch. A recurring rule the fleet is told to follow must be
readable and diffable in the tree, so a regression is caught by a gate, not re-discovered when a cron
silently stops.

## The gate

`scripts/check_cron_drift.py` (make target `check-cron-drift`, host-only like its sibling
`check-tick-prompt`) reads the two committed copies under `agents/llgenie-planner/prompts/` and compares
each against the live job's `prompt` in `$HOME/.hermes/profiles/llgenie-planner/cron/jobs.json`.

- **exit 0** — every checked live prompt equals its versioned copy;
- **exit 1** — any differs, naming the drifted job and BOTH byte counts, so the magnitude is visible;
- **exit 2** — the live jobs.json, a job, or a versioned copy is missing or unreadable (never a
  silent "no change").

Job-to-file is a two-row table in the script (`CRON_JOBS`), one row per live planner job — the same
extension point `check-tick-prompt` gives; the orchestrator tick is deliberately excluded here because
it has its own gate and its own committed path.

## Proof (real live bytes)

- **PASS, byte-synced:** committed copies equal the live prompts (`1658 b` and `2194 b`) →
  `[check-cron-drift] OK db0a3e1a3d7c … OK 71c5192ebdba … 2 job(s) checked`, `rc=0`.
- **FAIL on drift:** a diverged `llgenie-auto-approve-merge.md` →
  `[check-cron-drift] DRIFT db0a3e1a3d7c: LIVE prompt (1658 b) != versioned copy … (62 b)` and
  `rc=1`, while the intact sibling still reported `OK`.

## Coordinate

The documentation-maintainer lane owns committing the two prompt files (issues #2359 AC 1); this lane
owns the gate. The gate's versioned paths match the job names
(`agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md` and
`llgenie-auto-rebase-resolve.md`), so once those files land the gate passes on a synced host.
