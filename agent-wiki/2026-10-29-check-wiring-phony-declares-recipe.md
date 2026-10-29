# check-wiring-phony-declares-recipe — 2026-10-29

Issue: [#883](https://github.com/asimov-agent/llgenie/issues/883) · PR: this branch
(`fix/883-phony-declares-recipe`).

## What changed

- `scripts/check_wiring.py` — the `.PHONY` half is now bidirectional (the called→exists and
  declared→`.PHONY` directions already existed from #237/#392):
  - `_runs_something(block)` — a goal line runs something when it carries a recipe line (TAB), an
    inline `;` command, or at least one prerequisite (a declared alias). Comments are stripped before
    the header is read, so `loop: loop-harness ## alias` is an alias, not debris.
  - `graph()` exposes `phony_no_target` and `phony_runs_nothing`, derived from the two Makefiles.
  - `check()` names every offender in one pass, split by shape (no target at all vs a target that runs
    nothing), each with the fix that matches it.
  - `report()` prints the can-run / no-target / runs-nothing counts.
- `tests/test_wiring.py` — four tests: the measured no-target case (plus real `make` proving exit 0),
  all offenders in one pass, both alias shapes, and the real tree (derived, never a hand list).
- Docs: the `check-wiring` `##` line + `make help` text, `README.md`, `docs/BOTS.md` (its `.PHONY`
  section gains the reverse direction) and `docs/ARCHITECTURE.md`.

## Decisions

- **The issue's stated failure mode is wrong, and the correction is the reason the gate matters.**
  A `.PHONY` key with no rule does NOT fail with `No rule to make target`: because the name is
  declared phony, `make <name>` prints `make: Nothing to be done for '<name>'.` and exits **0**
  (measured in a scratch tree, and pinned in the test). The same name with no `.PHONY` entry fails
  exit 2. So the stale key is a permanent green no-op — the #392 hazard with no file needed to
  shadow it — not a loud error. The issue and the docs were updated to say that.
- **An alias is legitimate.** On `main@7e99e199` the four recipe-less `.PHONY` keys are
  `all: generate-requirements venv-install`, `loop: loop-harness`, `venv: create-venv` and
  `generate-build-engine-params: generate-engine-params` — all declared aliases, so the measured
  offender count on `main` is **0**. The rule is therefore a derived invariant with a negative
  control, not a fix list.
- **No Makefile hygiene was needed** — only the two `check-wiring` help lines changed, which keeps the
  diff small in a file 16 open PRs touch.

## Verified

- `tests/test_wiring.py` in `llgenie/test:latest`: **16 passed**.
- Negative control on the real tree: plant `ci-scope-phantom-883` in `.PHONY` → `make check-wiring`
  exits non-zero naming it; plant `phantom-dead-883` with a recipe-less, prerequisite-less target →
  exits non-zero naming it with the "runs NOTHING" message; restore → exit 0 with the original
  `OK … 261 make targets, CI calls 99 of them` line.
- `make check-wiring`, `make check-workflows`, `make check-docs`, `make lint`,
  `make openspec-validate NAME=fix-883-phony-declares-recipe` — all exit 0.
