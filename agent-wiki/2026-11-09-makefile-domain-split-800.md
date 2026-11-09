# 2026-11-09 — Makefile domain split into mk/*.mk + script entry points (#800)

The 2,083-line single `Makefile` became the split build: a short top `Makefile`
(shared env, `.PHONY`, `help`, `version`, and six `include mk/*.mk`) plus
`mk/{engines,gates,ci,security,bots,install}.mk` — target names and recipes
byte-for-byte unchanged (`make -qp` 373 sorted-unique targets identical both
sides, `make help` byte-identical).

The wiring gate landed in the split: `scripts/check_wiring.py` now resolves
`include mk/*.mk` before building its graph, and adds the two new findings —
a target declared in more than one included `mk/*.mk`, and a domain file over
its stated line budget (`MK_LINE_BUDGET`), so the monolith cannot quietly grow
back (the merge-conflict-class defect #460's state). A recipe that runs a
script whose `STEPS` names make targets acquires those edges (`_script_steps`),
so moving a 49-line `$(MAKE)` sequence into a module does not orphan the gate
coverage.

Five longest recipes (after `help`, which stays in the top Makefile) moved
their inline snippets into tested `scripts/<stage>.py` entry points, each
recipe <= 3 lines:

- `ci-unit` 49 lines -> `scripts/ci_unit.py` (the STEPS list runs every gate in
  order, stop-at-first-failure, exit with that step's status);
- `test-clean` 15 -> `scripts/test_clean.py` (prune stopped orphaned
  `llgenie/test` containers, never a running test, docker/nerdctl-agnostic);
- `build-server` / `build-variant` 15/13 -> `scripts/build_server.py` (detect
  or explicit tree/backend, build via `build_llama_server.sh`, verify the
  binary is executable, stamp `SERVER_BIN_STAMP`);
- `secret-scan` 13 -> the remediation text by exit-code lives in
  `scripts/secret_scan.py` main; the recipe is the one-line call.

Each module has unit tests (`tests/test_ci_unit.py`, `test_test_clean.py`,
`test_build_server.py`) that prove the behaviour (run order, prune-only-
stopped, stamp-write, loud failure on a missing binary), and
`tests/test_wiring.py` gained the three split findings tests (moved-target
stays wired, duplicate-across-includes is a finding, over-budget is a finding)
plus a moved-gate self-wiring pin.

Issue: #800. PR: (opened by this change). Related: #460, #237, #392, #883.
