# makefile-agents-mk — Spec Delta

## ADDED Requirements

### Requirement: The fleet/agent plumbing surface lives in mk/agents.mk

The repository SHALL keep the fleet/agent plumbing surface in `mk/agents.mk`, included from the
top Makefile, with every target name, `##` help line, and recipe byte-identical to the pre-split
top Makefile. The file SHALL contain exactly these 30 targets: `hermes-skills-register`,
`sync-agent-profile`, `provision-agent-profiles`, `skill-parity`, `tester-fold-live`,
`profile-drift-alarm`, `check-cron-drift`, `verify-lane-contract`, `profile-drift`, `lane-preflight`,
`_agent-shell-keys-check`, `agent-shell-keys-check`, `agent-fetch`, `_agent-fetch`, `search-smoke`,
`agent-jev-preflight`, `jev-preflight-required`, `agent-repo-ownership`, `hermes-smoke`,
`_agent-jev-preflight`, `_hermes-smoke`, `nerve-profile-check`, `check-main-ruleset`,
`main-ruleset-report`, `main-ruleset-apply`, `bind-proof`, `memory-install`, `memory-bootstrap`,
`memory-verify`, `memory-check`. Membership is decided by recipe shape, not name: `agent-image-ref`
runs a `scripts/ci_images.py` call and therefore belongs to the images domain (`mk/images.mk`), not
here; `bind-proof` binds a proof run's head to a PR head (an agent-pipeline leg) and belongs here.

#### Scenario: the include block lists the agents file

- **Given** the repository at a commit after this change
- **When** the top Makefile is parsed by `make -qp`
- **Then** `mk/agents.mk` appears among the included makefiles and all 30 targets listed above
  are defined exactly once across the whole include set

#### Scenario: moved recipes are byte-identical

- **Given** the pre-split top Makefile at the change's base commit
- **When** each of the 30 target blocks (attached comments through the final recipe continuation
  line) is compared to the same block in `mk/agents.mk`
- **Then** the comparison is byte-identical for every block

### Requirement: The split changes no observable make behavior

The split SHALL preserve `make help` byte-for-byte and SHALL NOT change any target's behavior;
the variables and macros the moved recipes read (`AGENT_SHELL_KEYS`, `AGENT_SHELL_FORWARD`,
`AGENT_SHELL_FORWARD_PLAIN`, `AGENT_IMAGE`, the `scrubbed_run` machinery and `HERMES_LOG*` names),
banners, `.PHONY` declarations, `help`, and `DEFAULT_GOAL` remain in the top Makefile, as in
`mk/engines.mk`, `mk/ci.mk`, `mk/gates.mk`, `mk/install.mk`, `mk/security.mk`, `mk/bots.mk` and
`mk/tests.mk` (all of which declare zero top-level variables). `mk/agents.mk` SHALL declare zero
top-level variables itself.

#### Scenario: help output identity

- **Given** the same repository before and after the split at the same base content
- **When** `make help` runs on both trees
- **Then** the two outputs are byte-identical, including the eight targets that carry no `##` line
  by design (the `_`-prefixed internal legs and the `memory-*` quartet)

#### Scenario: no target is declared twice

- **Given** the top Makefile and every file in `mk/`
- **When** target declarations are collected across the whole include set
- **Then** no target name appears in more than one file (the #2674 duplicate guard's unit mirror),
  and no moved agents target is re-declared in another domain file

### Requirement: The agent-lane guards survive the move intact

Every moved agent guard SHALL keep its wiring: the keys probe `agent-shell-keys-check` SHALL still
run `scripts/agent_shell_keys_check.py` inside the agent image with the forced-forward seam
`$(AGENT_SHELL_FORWARD)`, and `lane-preflight` SHALL still aggregate the same fast gates as before
the move.

#### Scenario: the keys probe is still a moved target

- **Given** `mk/agents.mk` after the split
- **When** the file is read
- **Then** it names `agent_shell_keys_check.py` and carries `$(AGENT_SHELL_FORWARD)` in the agent
  legs it moved
