# fix-bot-nopr-guard — spec of record

## ADDED Requirements

### Requirement: a no-PR "nothing to fix" dispatch is a clean skip

A `workflow_dispatch` of `.github/workflows/fix-bot.yml` that resolves no open PR branch (or resolves
a branch named main/master) MUST complete with `conclusion=success` and skip the whole agent leg —
it MUST NOT try to load or run anything from a workspace that has no checkout. In particular, the
agent-leg preflight step, the sync step and the transcript-upload step MUST carry
`steps.pr.outputs.branch != ''`, and the upload MUST be `always() && steps.pr.outputs.branch != ''`
(a plain `always()` reddens the no-PR path the moment the composite cannot load). This is the same
guard the checkout and the loop already carry, never weakened.

#### Scenario: no branch is resolved
- **WHEN** the `Resolve the PR branch` step prints `nothing to fix` and exits 0 with no `branch` output
- **THEN** the agent-leg preflight, the sync and the transcript upload are all skipped
  (`steps.pr.outputs.branch != ''` evaluates false), and the run concludes `success`

#### Scenario: a branch is resolved
- **WHEN** the resolve step emits a non-empty `branch`
- **THEN** the preflight, the sync, the loop and the upload each run exactly as before the change,
  with the upload guarded `always() && steps.pr.outputs.branch != ''`

### Requirement: the guard is locked by a regression test

`make test-unit` MUST hold the empty-branch case: `tests/test_fix_bot_nopr_guard.py` MUST read the
`fix` job of `.github/workflows/fix-bot.yml` and fail when any checkout-needing leg step (the agent-leg
preflight, the sync, the upload) loses the `steps.pr.outputs.branch != ''` guard.

#### Scenario: the guard is removed
- **WHEN** a checkout-needing leg step drops its `if: steps.pr.outputs.branch != ''`
  (or the upload's `always()` loses the `&& steps.pr.outputs.branch != ''` conjunct)
- **THEN** `tests/test_fix_bot_nopr_guard.py::test_no_pr_leg_steps_run_from_an_empty_workspace` fails,
  naming the step, and the negative-control test confirms the check catches the pre-fix shape
