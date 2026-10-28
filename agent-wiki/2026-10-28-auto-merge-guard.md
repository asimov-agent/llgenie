# The merge path cannot be removed silently

Issue #874. Auto-merge was switched off by hand during the "kill the pipelines" pause and nothing in the
tree failed: the file was still there, the workflow read `disabled_manually`, and green PRs accumulated at
`BLOCKED`. The behaviour is now permanent policy *and* guarded — deleting the file, deleting its automatic
trigger, or loosening the decision are each a red `ci-unit`.

## What was verified

- **The tree half.** `tests/test_bot_pipeline_isolation.py` gains
  `test_the_auto_merge_workflow_is_in_the_tree_and_keeps_its_name` (the file exists and is still named
  `auto-merge`, because `on.workflow_run.workflows` is matched verbatim) and
  `test_auto_merge_fires_by_itself_when_a_pr_run_completes` (an automatic PR-completion trigger —
  `workflow_run`/`check_suite`, naming `CI` with `types: [completed]` — plus a `merge` job whose `if:` still
  requires a pull-request run that concluded `success`). The second test collects every violation and reports
  them together, so one sabotage names all of the broken properties.
- **The decision half.** `tests/test_auto_merge.py::test_the_merge_gate_still_requires_a_clean_pr` pins
  `REQUIRED_STATE = "OPEN"`, `REQUIRED_MERGEABLE = "MERGEABLE"`, `REQUIRED_MERGE_STATE = "CLEAN"` and the
  `do-not-merge` hold, and then drives `decide()` for `UNSTABLE`, `BLOCKED`, `DIRTY`, `BEHIND`, `HAS_HOOKS`,
  `UNKNOWN` and the empty state (each must defer) plus the `CLEAN` control (must merge).
- **Sabotage, not existence.** With `on.workflow_run` removed: 2 failures (`test_auto_merge_fires_by_itself…`
  and `test_the_merge_is_a_workflow_run_on_ci`). With the file deleted: 3 failures in the workflow-invariant
  module plus a collection error in `test_auto_merge.py`. With `REQUIRED_MERGE_STATE = "UNSTABLE"`: 1 failure
  naming the loosened constant. Restored: `80 passed` over the four workflow/merge modules.
- `docs/BOTS.md` states green ⇒ merged as permanent policy, lists the paused bot fleet (measured with
  `gh workflow list --all`), and says `auto-merge` is never paused.

## Decisions

- **A repo-level `disabled_manually` is not testable from the tree**, and the guard does not pretend
  otherwise: that state lives in GitHub's API and only an owner can set it. What is guarded is everything the
  repository itself controls — the file, its automatic trigger, the job's green gate, and the threshold.
- **The cron is a backstop, never the trigger.** `3,33 * * * *` retries a deferral; accepting it as the
  automatic trigger would let a manual-only workflow look guarded.
- **`allow_auto_merge` stays owner-blocked.** It is `false` on `asimov-agent/llgenie` and no bot has admin,
  so #874's owner half is recorded as not done rather than claimed.
- The `docs/BOTS.md` opening sentence said the merge ran as a job in `ci.yml`; #493 moved it to
  `auto-merge.yml`, and the doc now says so.

## Status

Implemented on `ci/874-auto-merge-guard` (issue #874). Gates: `make check-workflows check-wiring lint
check-docs` exit 0; the four workflow/merge test modules `80 passed` in `llgenie/test:latest`.
