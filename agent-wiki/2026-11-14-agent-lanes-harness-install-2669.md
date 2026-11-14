# 2026-11-14 — agent lanes install: one seam, resolution proof, host cron rule (#2669)

OpenSpec change: `agent-lanes-harness-install-2669` (validated, rc=0). Issue: #2669.

## What was verified

- **The two-path install defect, measured.** `containers/agent/Dockerfile` populated every fleet lane
  with an inline `cp -r` loop (the #2181 step) while the host used `scripts/provision_agent_profiles.py`
  (#2165). The build gate `scripts/agent_lanes_check.py` proved only `SOUL.md` presence. Live proof of
  the gap: `find agents/llgenie-planner/skills -name SKILL.md` is non-empty, yet
  `hermes -p llgenie-planner skills inspect llgenie-bot-orchestration` exits non-zero — the tree's
  skillbooks were not in the lane's resolved set.
- **One seam now.** The Dockerfile lane step runs
  `provision_agent_profiles.py --root /opt/llgenie/agents --dest ${HERMES_HOME}/profiles --resolve`
  then the deepened `agent_lanes_check.py`; no executable `cp -r` remains. The three seam scripts the
  build runs joined the agent image hash inputs in `ci_images.py`, so an installer edit moves the tag.
- **`--resolve` proof.** For every manifest lane, each tree `skills/**/SKILL.md` directory must appear
  in `hermes -p <lane> skills list --source local` (elided table names count via prefix+ellipsis);
  unresolved → rc 1 naming lane + skill, resolver CLI missing → rc 2, never a silent pass.
- **Deepened gate.** `_skill_findings()` compares the tree's skills subtree to the installed home:
  missing subtree names the lane and its skill dirs; a byte-diverged `SKILL.md` names the lane and the
  relative path.
- **Host behavior rule (owner directive 2026-11-14).** `AGENTS.md` carries "Hermes cron jobs never run
  on the host (MANDATORY, durable)": profile cron stores stay empty/paused, the kanban worker pool
  stays closed, scheduled legs exist only as CI `schedule:` lanes. Proven on the live host the same
  day: 3 planner cron legs paused, 44 kanban tasks cancelled, 0 worker processes after settle.
- **Tests.** `tests/test_agent_lanes_check.py` +4 skill-finding tests, `tests/test_provision_agent_profiles.py`
  +6 resolve/hash-wiring tests. Hermetic proof: `docker run llgenie/test:latest pytest
  tests/test_agent_lanes_check.py tests/test_provision_agent_profiles.py -q` → **26 passed**, rc=0.

## Decisions

- No new `agent_lanes_install.py`: the existing host seam was extended instead — creating a third
  installer would re-create the very defect class #2669 names (the issue body was synced to match).
- `agents/` tree content stays untouched (owner directive); cron stores remain runtime state, no cron
  manifest joins the tree (durability of the restored tick lives in #2653).
- The #2664 live-prompt commit stays that issue's own task; this change makes the drift class gate-visible.

## Current status

Branch `feat/agent-lanes-harness-install-2669`; local gates green (validate rc=0, 26 tests green);
PR against upstream `main` pending lane-preflight + CI.
