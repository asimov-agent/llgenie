# registry-sync-spawn

## ADDED Requirements

### Requirement: The per-engine spawn runs whatever the gate above did

`registry-sync.yml`'s spawn step SHALL carry the condition `always() && steps.diff.outputs.changed`,
so a red check step above it cannot suppress the per-engine tracking issues, while a run with no
change still files nothing. The step's recipe SHALL re-check the watched store diff and exit 0 before
calling `make spawn-engine-skill-issues` when there is none.

WHEN the sync's check step fails on a store that names an unresolved engine
THEN the spawn step SHALL still execute and leave one tracking issue (or one `existing`/`created` log
line) per unresolved engine; and WHEN the store did not change
THEN the step SHALL run nothing and open no issue.

#### Scenario: a red gate still spawns the per-engine work items

Given a synced store that names an engine with no skill and no dated decision
And   the check step above the spawn has failed
When  the sync job reaches `Spawn one tracking issue per NEW unskilled engine`
Then  the step executes (its condition is `always() && steps.diff.outputs.changed`, never the check
      step's outcome) and prints a line per unresolved engine.

- **Test:** `tests/test_engine_skill_gap.py::test_the_spawn_step_runs_even_when_a_gate_above_is_red`

#### Scenario: no change, no filing

Given a sync checkout whose watched store files are unchanged
When  the spawn step's recipe runs
Then  it prints that there is nothing to spawn, exits 0, and `make spawn-engine-skill-issues` is never
      invoked — `always()` does not turn a no-change run into a filing.

- **Test:** `tests/test_engine_skill_gap.py::test_the_spawn_recipe_files_nothing_without_a_diff`

#### Scenario: a change runs the target

Given a sync checkout with a modified `data/models.json`
When  the spawn step's recipe runs
Then  `make spawn-engine-skill-issues` is invoked, so the diff guard skipped only the no-change run.

- **Test:** `tests/test_engine_skill_gap.py::test_the_spawn_recipe_files_nothing_without_a_diff`

### Requirement: The PR step stays gated on the change alone

`Open / update the sync PR` SHALL keep `if: steps.diff.outputs.changed` and SHALL NOT carry `always()`,
because pushing files whose checks did not pass is the one behaviour that must not become
unconditional.

WHEN the spawn step runs on a red gate
THEN the PR step SHALL NOT run, and a no-change run SHALL NOT open or edit a PR.

#### Scenario: the PR is never opened or pushed on a red run

Given a sync run whose check step failed
When  the sync job reaches `Open / update the sync PR`
Then  the step is skipped, because its only condition is the change flag.

- **Test:** `tests/test_engine_skill_gap.py::test_the_spawn_step_runs_even_when_a_gate_above_is_red`
