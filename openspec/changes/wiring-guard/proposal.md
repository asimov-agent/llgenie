# wiring-guard — proposal

Issue: [#237](https://github.com/asimov-agent/llgenie/issues/237)

## Why

`AGENTS.md` requires every verification to run through the Makefile ("All verification —
locally and in CI — MUST run through the Makefile"; "a Python test that exists with no
corresponding `make` target to drive it is a defect"; "A new test file is invisible until a
make target names it"). Nothing enforced any of it, and the tree already had the defect:
`tests/test_engine_bump_build.py` was named by **no** target, chain or workflow step — it
ran in no gate at all while reading as coverage.

This is the llgenie half of the guard already built for `trending-local-llms` (that repo's
`tests/test_validate.py::test_every_check_is_wired_to_a_stage_and_a_makefile_target` plus
rule 6d "No dead code — every Python entry point is wired to the Makefile"), whose PR
explicitly named "applying the same wiring rule to llgenie's own scripts" as a separate
change that was never filed.

## What Changes

- **`scripts/check_wiring.py`** — the wiring graph of the real tree: make targets (with
  their prerequisites), makefiles (`Makefile`, `tools/Makefile`), workflow steps, and each
  document's python dependencies (imports, plus the paths a document runs or reads; a path
  named only to assert its ABSENCE wires nothing). Two questions, both answered from the
  files: is a document wired to any target at all, and is it reached by the targets the CI
  workflows actually call.
  - `report` — how each document is wired, and the recorded host-only decisions;
  - `check` — exit 1 on a document wired to nothing, a document only a non-CI target
    reaches with no recorded decision, a stale decision (CI reaches it now, or the file is
    gone), or a workflow that calls a make target which does not exist (a typo in a `run:`
    block is a silent no-op today).
- **`tests/fixtures/host-only-wiring.json`** — the deliberate exceptions: a document a
  human runs by hand (native-Metal engines, the installed-launcher health check), with the
  reason, the target a human runs and the date. An omission has to be a decision — the same
  shape as `data/unsupported-engines.json` for unshipped engines.
- **`make check-wiring` / `make wiring-report`**, and `ci-unit` runs the check, so the
  regular PR pipeline fails on the next dead file instead of a reviewer catching it by eye.
- **The live defect is closed**: `tests/test_engine_bump_build.py` is deleted (the real
  llama.cpp cpu image build it asserted is the `engine-image-llama.cpp-cpu` matrix job, run
  on every push), and the stale `ci.yml` comment that claimed the serve stage pytest-runs
  `tests/test_engine_runs.py` directly now points at `scripts/engine_smoke.py --image`,
  which is what actually runs it.

## Not covered

- The dead **target** the same audit found: `make test-install-ci` (and with it
  `test-install-host`, `test-health-host`, `test-install-trend`) is called by no CI job,
  while its own docstring says the CI pipelines run it — its own issue.
- Wiring a *function* inside a script (`def` reachability) — this change covers documents
  and targets, which is where the repo's rule was being broken.
