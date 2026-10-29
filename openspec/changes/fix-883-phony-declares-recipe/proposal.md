# fix-883-phony-declares-recipe — proposal

Issue: [#883](https://github.com/asimov-agent/llgenie/issues/883)

## Why

`make check-wiring` verified one direction of the Makefile wiring: every target a workflow calls
exists, and every target is declared `.PHONY` (issue #392). The **reverse** direction was unchecked —
a `.PHONY` key whose recipe is gone, or never existed, passed every gate.

Measured while dropping a rebased commit (`ci-scope` re-added to `.PHONY` only):
`make check-wiring` printed `OK … 261 make targets, CI calls 99 of them` and exited 0. That shape is
not hypothetical: the documented union-resolution rule for two lanes' additions is "keep both keys in
`.PHONY`", so when one of those commits is later dropped the key survives the recipe.

The consequence is worse than the issue recorded. A `.PHONY` key with no rule does **not** fail at
run time: because the name is declared phony, `make <name>` prints
`make: Nothing to be done for '<name>'.` and exits **0** (measured; the same name with no `.PHONY`
entry fails `No rule to make target`, exit 2). It is a permanent green no-op that needs no file to
shadow it — the #392 hazard with no file required.

## What Changes

- **`scripts/check_wiring.py`** — the `.PHONY` half becomes bidirectional:
  - every `.PHONY` entry MUST name a target that can run: a recipe line, an inline `;` command, or at
    least one prerequisite (a declared alias such as `loop: loop-harness` /
    `all: generate-requirements venv-install`);
  - a key with no target at all, and a key whose target has neither a recipe nor a prerequisite, are
    both errors — every offender is named in the SAME pass, so one edit fixes the set;
  - `graph()` exposes `phony_no_target` / `phony_runs_nothing`, `report` prints the can-run /
    no-target / runs-nothing counts, and `check` names each offender with the fix that matches its
    shape.
- **`tests/test_wiring.py`** — four tests: the measured no-target case (and the real `make` output
  that proves it exits 0), all offenders in one pass, the two legal alias shapes, and the real tree
  derived from the Makefiles.
- **Docs** — the `check-wiring` help line, `README.md`, `docs/BOTS.md` (its own `.PHONY` section
  gains the reverse direction) and `docs/ARCHITECTURE.md` state the new rule and its measured
  failure mode.

## Not covered

- `.PHONY` style (ordering, grouping, alphabetical, duplicate keys) — no gate; a duplicate key is
  make-legal and this change does not police it.
- The inverse set-equality question ("every recipe that is meant to be phony is declared") — already
  gated by #392's rule, whose remaining gap is the `not_phony` decision file, not this change.
- CI job selection — this is Make wiring only.
