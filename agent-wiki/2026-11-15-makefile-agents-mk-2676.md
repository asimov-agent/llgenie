# Makefile agents-domain split — mk/agents.mk (issue #2676, PR via branch `feat/2676-makefile-agents-mk`)

Date: 2026-11-15. Issue: #2676. PR: branch `feat/2676-makefile-agents-mk` -> main. OpenSpec change: `makefile-agents-mk`.

## What was verified (against the issue and the #800 residual checklist)

- **Roster (30, by recipe):** the issue's 31 candidates minus `agent-image-ref` — its recipe is
  `scripts/ci_images.py latest agent`, an image ref, so it belongs to `mk/images.mk` (#2678, PR
  #2697), exactly as the issue's membership note pre-authorizes ("place by recipe, not name").
  `bind-proof` (borderline in the issue) moved here: its recipe binds a proof run's head to a PR
  head — an agent-pipeline leg.
- **Pure move:** blocks (attached comments → declaration → wrapped comment continuation → recipe
  continuations) extracted byte-identically; `make help` byte-identical (`cmp` rc=0, 59 lines);
  `make -qp` sorted-unique target inventory 580 → 581 at base `dcfb96b7df`, the sole diff line the
  `mk/agents.mk:` include record; declared-target grep 81 → 51 (30 in `mk/agents.mk`); zero dual
  declarations (the #2674 guard's unit mirror is in the new test module).
- **Variables stay at the top:** `AGENT_SHELL_KEYS`, `AGENT_SHELL_FORWARD(_PLAIN)`, `AGENT_IMAGE`,
  the `scrubbed_run`/`HERMES_LOG*` machinery remain in the top Makefile; `mk/agents.mk` declares
  zero top-level variables (the six-sibling convention). Recipe expansion proven by
  `make -n lane-preflight memory-check search-smoke agent-shell-keys-check` (rc=0).
- **8 targets carry no `##` help line by design** (four `_`-prefixed internal legs, the `memory-*`
  quartet) — pinned as `NO_HELP_ON_PURPOSE` so a future edit can't accidentally promote them into
  `make help`.
- New `tests/test_makefile_agents_mk_split.py`: 8 pins, all green locally.

## Key decisions

- Include order: `mk/agents.mk` appended after the current last include (rebase resolves position
  against `mk/images.mk` from #2678).
- `.PHONY` lines, banners, `help`, `DEFAULT_GOAL` untouched in the top file (per #2456–#2461).

## Current status

Split verified locally (inventory/help/roster pins + `make check-wiring` OK); full unit suite and
CI run at head. #800 criterion 4 moves 30 targets closer: top-file residuals 51 after this change.
