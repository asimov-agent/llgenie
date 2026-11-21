# Tasks: verdict-artifact-skip-2991

## 1. Gate/behavior

- [x] 1.1 `scripts/auto_merge.py`: name the verdict lane's workflow file (`VERDICT_ARTIFACT_FILE = "ci-verdict.yml"`, mirroring `ci_verdict.OUR_WORKFLOW_FILE` #2221) and give `failing_checks` a `trigger_green` mode that clears a concluded-red row of THAT FILE with a named `stale verdict artifact (not a block)` note, leaving every other red blocking.
- [x] 1.2 Thread `trigger_green` through `run`, `_clear_review` and `_merge_review_cleared` re-reads; expose `--trigger-green` on the `auto-merge` subcommand.
- [x] 1.3 `mk/bots.mk`: `make auto-merge` gains `TRIGGER_GREEN=1`; `auto-merge.yml` passes `TRIGGER_GREEN=1` on the `merge` job step (its `if` gate proves `workflow_run.conclusion == 'success'` at this head) and the header documents the rule beside the #2885 collapse.

## 2. Tests

- [x] 2.1 Sweep-level test: the measured wedge (stale `ci-verdict.yml` artifact red beside an all-green CI attempt) merges under `trigger_green=True` and the log names the cleared row.
- [x] 2.2 Strictness tests: the same head without `trigger_green` defers naming the artifact; a red `ci-verdict` JOB row of `ci.yml` defers even with the trigger; a foreign red (issue-bot `implement`) defers even with the trigger.

## 3. Verify

- [x] 3.1 `make openspec-validate NAME=verdict-artifact-skip-2991` exits 0.
- [x] 3.2 The focused battery `tests/test_auto_merge.py` (in `llgenie/test:latest`) passes, replaying the #2990 wedge fixture.
- [x] 3.3 `make test-unit` exits 0 with the new tests included in the full hermetic battery.
