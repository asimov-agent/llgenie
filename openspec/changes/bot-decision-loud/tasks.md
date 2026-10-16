# Tasks — bot-decision-loud

## The live swallow (issue #312)

- [x] `issue-bot.yml`'s dispatch step: consult `rc` and `exit 1` with an `::error::` naming
      `issue-bot-dispatch` and its rc, BEFORE the cap/none test reads an empty `action` as "proceed".
- [x] Confirm the other decision steps are already safe: `fix-bot.yml` runs its `make` as the step's
      command under `set -euo pipefail`; `rebase-bot.yml` (#310) and `issue-refiner.yml` (#316) carry
      the rc check.

## The rule and its guard

- [x] Add `tests/test_bot_decision_loudness.py`: table-driven over every workflow step that runs a
      decision target, running each step's own shell against a `make` that exits non-zero.
- [x] Read the rule's SCOPE from the tree (a new bot workflow is covered the moment it exists) and
      require `issue-bot.yml` / `issue-refiner.yml` / `rebase-bot.yml` in it.
- [x] Substitute a `${{ … }}` the way the runner does, so the loudness test cannot pass because bash
      tripped on an expression — and assert that substitution.
- [x] Assert the other direction: a decision that answers cleanly leaves the step green.
- [x] Wire `tests/test_bot_decision_loudness.py` into the `test-unit` recipe (a test file no target
      names runs in no gate).

## Tests

- [x] `tests/test_bot_decision_loudness.py::test_the_decision_steps_are_what_this_file_covers`
- [x] `tests/test_bot_decision_loudness.py::test_a_github_expression_in_a_step_is_substituted_before_it_runs`
- [x] `tests/test_bot_decision_loudness.py::test_a_crashed_decision_fails_the_step`
- [x] `tests/test_bot_decision_loudness.py::test_the_step_that_had_no_check_now_reports_the_crash`
- [x] `tests/test_bot_decision_loudness.py::test_a_decision_that_succeeds_leaves_the_step_green`
- [x] Rule-6c proof: on a pre-fix worktree (`origin/main` + the new test file) the loudness rule and
      the issue-bot case fail (**2 failed / 3 passed**); on this branch **5 passed**.

## OpenSpec

- [x] `proposal.md`, `specs/bot-decision-loud/spec.md`, `tasks.md` written.
- [x] `make openspec-validate NAME=bot-decision-loud` passes.

## Gates

- [x] `make lint` passes.
- [x] `make test-unit` runs the new file (wired in the same commit).
- [x] `make check-wiring`, `make check-docs`, `make check-workflows` pass.
- [x] The rest of the loop runs in CI on this branch.
