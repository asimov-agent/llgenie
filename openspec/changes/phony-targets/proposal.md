# Every target that produces no file of its own name is declared `.PHONY`

## Why

`make` decides whether to run a recipe by looking for a **file** with the target's name. A target
that produces no such file must be declared `.PHONY`, or any file carrying that name shadows it —
make prints `make: '<target>' is up to date.` and runs nothing, reporting success.

Measured on `main@f91d82f` (issue #392): 176 targets, 154 `.PHONY` entries, **22 undeclared**
(`bash-check`, `ci-install-run`, `engine-bump`, `generate-requirements`, `openspec-tasks-check`,
`test-env`, `test-top-tier*`, `test-native-engine*`, `test-variant-image`, …), and nothing compared the
hand-written `.PHONY` block against the targets that exist — not `check-wiring`, not `check-workflows`,
not `ci-unit`.

Reproduction, no edit needed:

```
$ touch test-env && make test-env     # "make: 'test-env' is up to date." — no recipe ran
```

## What Changes

- **The undeclared targets join the `.PHONY` block** (23 in total: the 22 above plus
  `generate-requirements-dev-venv` in `tools/Makefile`, which the same rule found when it ran).
- **The rule is enforced, not remembered**: `scripts/check_wiring.py` (which already parses every
  target and its prerequisites, and which `ci-unit` already runs) fails when a target is not declared
  `.PHONY`. A target that genuinely produces a file of its own name is recorded under a new
  `not_phony` section of `tests/fixtures/host-only-wiring.json` — a dated decision with a reason,
  refused without one, and **stale** the moment the target is declared or disappears.
- **`tests/test_wiring.py` pins it in both directions**: a scratch tree whose target is undeclared, and
  a real file carrying that name, where real `make` runs nothing and reports success — then the same
  tree with `.PHONY` added, where the recipe runs and the guard is clean. Plus the decision path
  (reason required, stale entries refused) and the real tree (no undeclared target, roster derived).
- `make wiring-report` prints how many targets are declared, recorded, and undeclared.

## Impact

- Affected specs: `wiring-guard` (new capability in this change).
- Affected code: `Makefile` (`.PHONY`), `tools/Makefile` (`.PHONY`), `scripts/check_wiring.py`,
  `tests/test_wiring.py`, `README.md`.

## Not covered (each its own issue)

- Making the `.PHONY` list itself generated (a target list derived at parse time) — the rule here makes
  an omission loud; generating the list is a bigger change and is not needed while the guard names it.
