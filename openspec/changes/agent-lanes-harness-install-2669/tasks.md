## 1. Installer seam extended

- [x] 1.1 Extend `scripts/provision_agent_profiles.py` with `--resolve` (injectable resolver, per-lane skill names, loud CLI-missing failure)
- [x] 1.2 `Makefile provision-agent-profiles` gains `RESOLVE=1` so the host runs the same proof

## 2. Gate deepened

- [x] 2.1 Extend `scripts/agent_lanes_check.py` with skills-subtree presence + per-SKILL.md byte findings

## 3. Image + hash wiring

- [x] 3.1 Replace the `cp -r` lane loop in `containers/agent/Dockerfile` with `provision_agent_profiles.py --resolve` + the deepened gate
- [x] 3.2 Add the scripts the build now runs to the agent image hash inputs in `scripts/ci_images.py`

## 4. Host behavior rule + issue sync

- [x] 4.1 `AGENTS.md` carries "Hermes cron jobs never run on the host (MANDATORY, durable)"
- [x] 4.2 Issue #2669 body synced with the implemented goal (harness seam + host cron rule)

## 5. Tests green

- [x] 5.1 Extended `tests/test_provision_agent_profiles.py` + `tests/test_agent_lanes_check.py` pass locally (26 passed in the hermetic test container)
- [x] 5.2 `make openspec-validate NAME=agent-lanes-harness-install-2669` exits 0
- [x] 5.3 Both test modules are selected by the hermetic unit-suite discovery: `python3 scripts/unit_tests.py list` names `tests/test_agent_lanes_check.py` and `tests/test_provision_agent_profiles.py` (rc=0), so the main CI unit stage runs them
