# Change: Split the fleet/agent plumbing targets out of the top Makefile into mk/agents.mk

## Why

Issue #2676 (residual of #800, one-issue-per-make-file rule): the top Makefile still declares the
fleet/agent cluster — the targets every agent lane runs (lane preflight, agent shell-keys probe,
agent fetch, JEV preflight, profile drift/sync, main-ruleset guards, memory bootstrap). Fleet and
agent PRs keep colliding in the monolith: this is the file half of what #800 was filed to defuse.
This completes the domain pattern of `mk/engines.mk` (#2456), `mk/gates.mk` (#2457), `mk/ci.mk`
(#2458), `mk/security.mk` (#2459), `mk/install.mk` (#2461), `mk/bots.mk` (#2460) and the tests
split (#2677, PR #2695) for the agents domain, following the same byte-identical-move playbook.

## What Changes

- **Moved (30 targets, recipes and `##` lines byte-identical):** `hermes-skills-register`,
  `sync-agent-profile`, `provision-agent-profiles`, `skill-parity`, `tester-fold-live`,
  `profile-drift-alarm`, `check-cron-drift`, `verify-lane-contract`, `profile-drift`,
  `lane-preflight`, `_agent-shell-keys-check`, `agent-shell-keys-check`, `agent-fetch`,
  `_agent-fetch`, `search-smoke`, `agent-jev-preflight`, `jev-preflight-required`,
  `agent-repo-ownership`, `hermes-smoke`, `_agent-jev-preflight`, `_hermes-smoke`,
  `nerve-profile-check`, `check-main-ruleset`, `main-ruleset-report`, `main-ruleset-apply`,
  `bind-proof`, `memory-install`, `memory-bootstrap`, `memory-verify`, `memory-check`.
- **Excluded by recipe (the issue's membership note):** `agent-image-ref` — its recipe is a
  `scripts/ci_images.py latest agent` call (image-shaped), so it belongs to the images domain
  (`mk/images.mk`, sibling issue #2678, PR #2697), not here. `bind-proof` is borderline in the
  issue's note; by recipe it binds a proof run's head to a PR head — an agent-pipeline leg — so it
  moves here.
- **Stayed:** all variables/macros the moved recipes read (`AGENT_SHELL_KEYS`,
  `AGENT_SHELL_FORWARD`, `AGENT_SHELL_FORWARD_PLAIN`, `AGENT_IMAGE`, `HERMES_LOG*`, the
  `scrubbed_run` machinery) — the domain files declare targets only, exactly as the six existing
  files; every `.PHONY` line; banners; `help`; `DEFAULT_GOAL`.
- `include mk/agents.mk` appended to the include block (after `mk/tests.mk` / `mk/images.mk`).
- New test module `tests/test_makefile_agents_mk_split.py` pins the split (membership, roster
  exactness, help-line retention except the eight targets that carry none at base, zero dual
  declarations, zero top-level variables in the domain file, `agent-image-ref` exclusion, keys-probe
  wiring intact).

## Impact

- Affected specs: `makefile-agents-mk` (new capability)
- Affected code: `Makefile` (pure move, −30 target declarations), `mk/agents.mk` (new),
  `tests/test_makefile_agents_mk_split.py` (new), docs rows.
- No CI workflow changes: every gate reader is already include-aware (#2456–#2461, #2677 precedent).
