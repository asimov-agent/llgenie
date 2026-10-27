# The per-engine spawn runs even when the sync's gate is red

Issue #758. Implements the OpenSpec change `registry-sync-spawn-always`.

## The defect

`registry-sync.yml`'s `Spawn one tracking issue per NEW unskilled engine` step carried
`if: steps.diff.outputs.changed` and nothing else, so it inherited the check step's failure. The run
that most needs the per-engine work items — a store naming an engine llgenie does not ship, whose
`test-unit` / `check-engine-skill-gap` therefore reds — is exactly the run where the step was skipped.
Measured on `origin/main` `930900b`, run `40554900569`: the check step failed (`36 failed, 14486
passed`), `State what changed in ONE issue` (`always()`) ran, the spawn and the PR step had no log at
all.

## What changed

- The spawn step is `if: always() && steps.diff.outputs.changed`, matching the change-issue step above
  it. `always()` is what makes it execute after a red gate; the `changed` term is what keeps a
  no-change run from filing.
- The guard is repeated *inside* the recipe, not only in the condition: the step runs
  `git diff --quiet -- <the watched store files>` and exits 0 with a log line when there is nothing to
  spawn. So `always()` cannot turn a no-change run into a filing even if the condition is later edited.
- `Open / update the sync PR` keeps `if: steps.diff.outputs.changed` alone. Pushing files whose checks
  did not pass is the one behaviour that must not become unconditional.

## Verification

- `tests/test_engine_skill_gap.py::test_the_spawn_step_runs_even_when_a_gate_above_is_red` — the
  condition is exactly `always() && steps.diff.outputs.changed`, the diff guard precedes `make` in the
  recipe, and the PR step carries no `always()`. Removing the `always()` reds this test.
- `tests/test_engine_skill_gap.py::test_the_spawn_recipe_files_nothing_without_a_diff` — the step's
  own recipe text is executed in a temp git checkout with a recording `make` on PATH: unchanged store →
  `make` never called; a modified `data/models.json` → the target is invoked.
- `make check-workflows`, `make check-dispatch-forms`, `make check-docs`, `make check-wiring` and
  `scripts/lint_linefeeds.py` green; the full discovered unit suite 14528 passed with one
  pre-existing, environment-only failure — `tests/test_repo_slug.py::test_the_documented_invocations_carry_the_slug`
  sees `make[1]: Entering directory '/repo'` because this bot shell inherits `MAKELEVEL=1`, and is 4/4
  green with it unset (the test container does not forward it). No container could start here (no
  Docker daemon), so the stdlib/pytest entry points behind `make lint` / `make test-unit` were run
  directly on the host; CI runs the wrapped targets.

## Decisions

- The per-engine `spawn` command already no-ops when nothing is unresolved (`no unresolved engine`) and
  is idempotent per engine (it re-reads the open issue by title), so no change was needed in
  `scripts/engine_skill_gap.py`; the missing piece was the step condition and the in-recipe guard.
- The live half of the acceptance ("a dispatched run with a red gate has the spawn step executed") is a
  post-merge observation on the next sync run; the hermetic proof here is the condition plus the
  executed recipe.
