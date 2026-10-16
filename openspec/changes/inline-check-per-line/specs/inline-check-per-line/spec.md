# inline-check-per-line

## ADDED Requirements

### Requirement: the inline-script check is per command, not per step block

`check_workflow_inline_scripts` MUST scan each command of a `run:` block individually: a command that
invokes a repo script (`python3 scripts/...`, `scripts/*.sh`) without a `make` on the same line MUST be
a finding, even when another line of the same step is `gh`/`git` orchestration. An orchestration-only
step MUST still pass, because such a line invokes no repo script.

WHEN a workflow step orchestrates with `gh` and calls a repo script on another line
THEN the check reports it, naming the script and the step.

#### Scenario: a gh step cannot hide a repo-script call on another line

- **Given** a step whose lines are `gh api …`, `python3 scripts/engine_skill_gap.py report --md`, `gh pr create …`
- **When** the check runs
- **Then** exactly one finding names `engine_skill_gap.py`
- **And** the same step with `gap="$(make engine-skill-gap-md)"` is not a finding
- **Test:** `tests/test_code_review.py::test_a_gh_step_cannot_hide_a_repo_script_on_another_line` and
  `tests/test_code_review.py::test_a_make_target_on_the_same_line_clears_a_script_call`

### Requirement: the real tree reaches its logic through make targets

Every step of every committed workflow MUST call a make target for repo logic, so the self-consistency
case runs the check over `.github/workflows` and requires no finding. `registry-sync.yml` MUST get the
markdown gap report through `make engine-skill-gap-md` rather than calling the script, and the test
that locks that step MUST pin the make target, not the script call it replaced.

WHEN the check runs over the real workflows
THEN it finds nothing, and the sync step it clears asks a make target for the gap markdown.

#### Scenario: no inline script call remains in the tree

- **Given** the committed workflows, including `registry-sync.yml`
- **When** `check_workflow_inline_scripts` runs over the repository
- **Then** it returns no finding, and `make engine-skill-gap-md` exists as the target the sync step calls
- **And** the sync workflow's PR body is built from that target, with no repo script called inline
- **Test:** `tests/test_code_review.py::test_the_real_tree_has_no_inline_script_call` and
  `tests/test_engine_skill_gap.py::test_the_weekly_sync_regenerates_the_gap_and_spawns_a_tracking_issue`

Note: the check reads steps through `_steps()`, which at the time of this change yielded only a
workflow's LAST `run:` block (#305); the scenario above was therefore satisfiable only for the last
step of each workflow. #305 — the separate change that makes every step visible — landed as PR #326
(`inline-check-all-steps`), so the scenario now holds for every step. Not in scope here.
