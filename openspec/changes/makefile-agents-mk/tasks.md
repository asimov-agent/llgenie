# Tasks: makefile-agents-mk

## 1. Baseline
- [x] 1.1 Record the pre-split baseline at the PR base: `make -qp` sorted-unique target list, `make help`, declared-target grep count (805 lines, 81 declared targets, 580 inventory at `dcfb96b7df`)
- [x] 1.2 Confirm the 30-target agents roster has zero overlap with the ci (#2458), bots (#2460), security (#2459), tests (#2677) and images (#2678) rosters

## 2. Split
- [x] 2.1 Extract the 30 agent-domain target blocks (attached comments → declaration → wrapped comment continuation → recipe continuation lines) byte-identically into `mk/agents.mk`; exclude `agent-image-ref` by recipe (image-shaped, rides `mk/images.mk` via #2678)
- [x] 2.2 Append `include mk/agents.mk` to the include block; leave banners, variables/macros (`AGENT_SHELL_KEYS`, `AGENT_SHELL_FORWARD`, `scrubbed_run` machinery), `help`/`.PHONY`/DEFAULT_GOAL in the top Makefile

## 3. Parity
- [x] 3.3 `make -qp` sorted-unique target lists identical to baseline except make's own record of the new include (`mk/agents.mk:` is the sole diff line); `make help` byte-identical (`cmp` rc=0); zero targets declared in both files; declared-target grep 81→51 with 30 in `mk/agents.mk`
- [x] 3.4 New `tests/test_makefile_agents_mk_split.py` pins membership, roster exactness, help retention (8 no-help-by-design), no-dual-declaration, zero domain-file variables, `agent-image-ref` exclusion, keys-probe wiring

## 4. Docs + gates
- [x] 4.1 `docs/ARCHITECTURE.md` `mk/` row names `agents.mk` citing #2676; `docs/changes.d/` row + CHANGES.md index; agent-wiki entry
- [x] 4.2 `make check-wiring`, `make check-docs`, `make openspec-tasks-check`, `make openspec-validate` green; full `make test-unit` green at head; `make lane-preflight` OK
