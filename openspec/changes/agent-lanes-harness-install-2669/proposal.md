# Proposal: agent-lanes-harness-install-2669

## Why

The agent image installs every fleet lane with an inline `cp -r` loop in `containers/agent/Dockerfile`, while the host installs the same `agents/` tree through `scripts/provision_agent_profiles.py` (the multi-lane wrapper over `agent_profile_sync.write/check`, issue #2165). Two code paths, one behaviour — and the image path is the untested one. The build gate that watches the result (`scripts/agent_lanes_check.py`) proves only that each declared lane's `SOUL.md` file is present: never that the lane's skills subtree landed byte-identically, never that Hermes can resolve those skills for the lane, and the seam that DOES byte-reconcile (provision) never runs inside the image. A container can therefore ship green while a bot lane runs without its skillbooks; the same drift class is live today as #2664 (tree vs live profile divergence, `check-agent-profiles` FAIL x2).

## What Changes

- **One installer seam, used by BOTH sides.** `scripts/provision_agent_profiles.py` (already the host's multi-lane entrypoint `make provision-agent-profiles`, and already reusing `agent_profile_sync.write/check`) becomes the ONLY lane installer. `containers/agent/Dockerfile` replaces its `cp -r` loop with this script (`--root /opt/llgenie --dest ${HERMES_HOME}/profiles --resolve`), so image and host install lanes through the same code, with the write-then-read-back byte reconciliation the image copy never had.
- **Resolution proof at build time.** `provision_agent_profiles.py` gains `--resolve`: for every declared lane it runs `hermes -p <lane> skills list --source local` and fails, naming the lane and the missing skill, when a skill the lane's tree carries (`skills/**/SKILL.md`) is absent from what Hermes resolves. The resolver is injectable (a callable returning the list text) so unit tests drive it without Hermes installed; the Dockerfile step uses the real CLI.
- **Deepened build gate.** `scripts/agent_lanes_check.py` gains findings: a declared lane whose installed home lacks a `skills/` subtree the tree carries, and a per-file byte comparison of every tree `SKILL.md` against the installed copy (missing or differing file names the lane and the relative path).
- **Hash input completeness.** `scripts/provision_agent_profiles.py`, `scripts/agent_profile_sync.py`, `scripts/check_agent_profiles.py` join the agent image's hash inputs in `scripts/ci_images.py`: the build now RUNS them, so a change to the installer must move the image tag (the rule that keeps "the image a job uses" the image of THIS commit).
- **Host behavior rule.** `AGENTS.md` gains "Hermes cron jobs never run on the host (MANDATORY, durable)": profile cron stores stay empty/paused, the kanban worker pool stays closed, scheduled bot legs exist only as CI `schedule:` lanes running the fleet image — the behavioral counterpart of installing lanes correctly into the image (owner directive 2026-11-14; the host was found with 3 active planner cron legs and 44 queued kanban tasks, both since stopped).

## Scope guard

- `agents/` tree content stays as it is: no cron manifests, no new lane files (owner directive 2026-11-14).
- The live prompt drift itself remains #2664's own task; this change makes the drift class *visible by gate*, it does not commit #2664's prompts.
- No inference server is started anywhere in this change.

## Impact

- Affected specs: `agent-lanes-harness` (new capability: image lane install through the single seam + gate + resolution)
- Affected code: `containers/agent/Dockerfile`, `scripts/provision_agent_profiles.py`, `scripts/agent_lanes_check.py`, `scripts/ci_images.py`, `Makefile` (`RESOLVE=1` flag on `provision-agent-profiles`), `tests/test_agent_lanes_check.py`, `tests/test_provision_agent_profiles.py`, `AGENTS.md`
