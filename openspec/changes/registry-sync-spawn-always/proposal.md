# The per-engine spawn runs even when the sync's gate is red

## Why

`registry-sync.yml` gives the engine-tracking step no `always()`, so the run that most needs it files
nothing. The check step (`make check-registry` + `check-quant-catalog` + `engine-skill-gap` +
`skills-validate` + `test-unit` against the new registry) carries `if: steps.diff.outputs.changed`, and
the spawn step carried the same condition and nothing else — so a red gate skipped it.

Measured on `origin/main` `930900b`, run `40554900569` (head `d190aed`): the check step failed with
`36 failed, 14486 passed`; the step before the spawn, `State what changed in ONE issue` (`if: always()
&& steps.diff.outputs.changed`), ran; `Spawn one tracking issue per NEW unskilled engine` and
`Open / update the sync PR` never did — the run has no step-11/12 log at all.

The deadlock is structural: a store that names an engine llgenie does not ship is exactly the store
whose `test-unit` / `check-engine-skill-gap` reds, and that red is what suppressed the per-engine
tracking issues the decision needs. #683 fixed the catalogue half (the sync carries the engine instead
of dying on it); this is the remediation half.

## What Changes

- **`.github/workflows/registry-sync.yml`** — the step `Spawn one tracking issue per NEW unskilled
  engine (runs even when a gate above is red)` carries `if: always() && steps.diff.outputs.changed`,
  matching the change-issue step above it, and its recipe re-checks the diff itself
  (`git diff --quiet -- <the watched store files>` → `exit 0` with a log line) so `always()` cannot
  turn a no-change run into a filing. The PR step keeps `if: steps.diff.outputs.changed` alone: a file
  the checks did not pass on is never pushed.
- **`tests/test_engine_skill_gap.py`** — two contract tests: the condition is exactly
  `always() && steps.diff.outputs.changed` with the guard in the recipe before `make` and the PR step
  still conditional; and the recipe is executed for real in a temp git checkout — no diff → no `make`,
  a diff → the target runs, so the guard is proven end-to-end and not just by string match.

## Impact

- A red sync run leaves the work item that explains how to un-red it, in the same run that fails.
- The engine decisions arrive as issues the moment the store names a new engine, so the blocker is
  actionable when it appears instead of expiring with the log.
- The PR step is untouched, so no unchecked file can reach a branch.
