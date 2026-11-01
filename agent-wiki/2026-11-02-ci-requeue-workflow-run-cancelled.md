# LLGenie Pipeline Maintainer: ci-requeue no longer aborts on a cancelled `workflow_run` run (#1451)

Implements issue #1451 (ready-for-review PR, never merged). `scripts/ci_requeue.py`'s `plan()`
selected a cancelled run for re-run based on `conclusion` + supersession only, and `rerun()` then
called `gh run rerun <id> --failed` on it. A run whose trigger is **`workflow_run`** (a reaction:
`auto-merge`, `ci-verdict`, `run-failure-reactor` completing) **cannot be retried** by GitHub — the
CLI answers `This workflow run cannot be retried` — and since `rerun()` raised, the whole
`make ci-requeue-cancelled` job aborted after the FIRST such run, healing **nothing** in the window.
Measured 2026-11-01 20:09Z (PR #1444 verification, ci-requeue dispatch run 41345358332): the heal
died on run 41345284767 (`auto-merge`, `head_branch=main`, `event=workflow_run`,
`conclusion=cancelled`) with `Makefile:919: ci-requeue-cancelled` Error 1.

## What changed (measured on this worktree, main `2998925a`)

- `scripts/ci_requeue.py` — `plan()` now passes a cancelled run whose `event == "workflow_run"` into
  the SKIPPED list with the explicit reason `workflow_run-triggered: GitHub will not retry this run`
  instead of the requeue list. A reaction's completion is not a verdict to heal — it cannot be
  retried (#286-adjacent: the reactor special-cases its own `workflow_run` origin). Every retryable
  cancellation in the window is still re-run.
- `tests/test_ci_requeue.py` — a fixture `_run_record` now carries `event`; two new tests,
  `test_a_cancelled_workflow_run_triggered_run_is_skipped_but_not_fatal` (the negative control: plant
  an auto-merge cancellation next to a retryable one, assert the retryable one is re-run and the
  auto-merge one is named, not fatal) and `test_plan_dry_names_a_cancelled_workflow_run_triggered_run`
  (AC2: the plan records the un-retryable run with its reason, never a silent list nothing).

## Verification (measured, not asserted)

- `/home/asimov/llama-gguf-tools/.venv/bin/pytest tests/test_ci_requeue.py -q`: **13 passed**
  (both new tests, all prior behaviour intact).
- **Negative control proved the guard catches the bug:** with the `plan()` guard reverted (buggy
  tree), both new tests FAIL — `test_a_cancelled_..._skipped_but_not_fatal` and
  `test_plan_dry_...` report `[602, 603] == [603]` / the workflow_run run lands in the requeue list.
  Restored, both pass.
