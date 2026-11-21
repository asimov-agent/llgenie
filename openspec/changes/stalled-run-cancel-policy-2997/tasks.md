# Tasks: stalled-run-cancel-policy-2997

## 1. Change and decision

- [x] 1.1 Open the OpenSpec change (proposal, spec delta, tasks) referencing issue #2997 and its measured run `44863652918` / job `136722618230`, stating the DECISION (cancels allowed under four named proofs; cancel is not queue-pumping) in `Why`/`What Changes`. (proven: `make openspec-validate NAME=stalled-run-cancel-policy-2997` rc=0)
- [x] 1.2 Record the same decision in the issue #2997 body (AC1) so the issue, the change, and the code agree. (proven: `gh issue edit 2997` rc=0 syncing the four-proof decision at head a609e7c10a1ed1a66a9417b1c217a489a119df5c)

## 2. Implementation (lands on top of the watchdog from PR #2992; rebase onto main once #2992 lands)

- [x] 2.1 `scripts/stalled_job_watchdog.py`: add `--cancel-stalled` — cancel BEFORE filing (so the comment states the real outcome), live re-read before each cancel (skip when the stalled job concluded), PR-head-only gate (OPEN non-draft PR), benign-race handling, `cancelled/skipped/race` outcome vocabulary. (proven: `~/llama-gguf-tools/.venv/bin/python3 -m pytest tests/test_stalled_job_watchdog.py -q` rc=0, 13 passed)
- [x] 2.2 `make check-stalled-jobs` gains the `CANCEL=1` -> `--cancel-stalled` knob by reference in mk/bots.mk; `.github/workflows/zero-job-pending.yml` passes it through the existing watchdog step (no new lane, no new clock). (proven: `make help` names `CANCEL=1`; the lane step runs `make check-stalled-jobs REPO=... FILE=1 CANCEL=1`)
- [x] 2.3 Pin the classified-verdict path with tests: a watchdog-cancelled PR head read by `ci_verdict` (cancelled in BLOCKING_CONCLUSIONS -> neutral verdict at the head) and by `auto_merge` (cancelled in RED_CONCLUSIONS -> deferral naming the conclusion). (proven: `test_a_watchdog_cancelled_stalled_row_reads_through_the_blocking_conclusion_path` + existing `test_the_blocking_conclusions_are_the_merger_s_rule` and `test_a_cancelled_or_neutral_check_defers_the_merge`; `pytest tests/test_ci_verdict.py -q` rc=0)

## 3. Tests (`tests/test_stalled_job_watchdog.py` extended, `gh` stubbed on PATH)

- [x] 3.1 AC2: a stalled run with `--cancel-stalled` is cancelled before filing; the filed comment names the cancel outcome. (proven: `test_cancel_stalled_cancels_the_pr_head_run_and_the_comment_names_it`, rc=0)
- [x] 3.2 A job that concluded between classification and cancel -> cancel SKIPPED, named skipped; no cancel invoked. (proven: `test_a_run_that_concluded_between_classification_and_cancel_is_skipped` + `test_a_concluding_job_on_an_in_progress_run_is_skipped_not_cancelled`, rc=0)
- [x] 3.3 A cancel racing a conclusion -> reported benign race, exit code unchanged. (proven: `test_a_cancel_that_races_a_conclusion_is_benign`, rc=0)
- [x] 3.4 No-PR run (schedule/push) -> named only, never cancelled; draft or closed PR head -> never cancelled. (proven: `test_no_pr_draft_and_closed_heads_are_never_cancelled`, rc=0)
- [x] 3.5 No `rerun`/`dispatch`/re-trigger is ever invoked by the cancel path (negative control on the stubbed `gh`). (proven: `test_the_cancel_path_never_dispatches_reruns_or_retriggers` reads the stub's CALLS journal, rc=0)

## 4. Docs

- [x] 4.1 `docs/changes.d/` fragment + `agent-wiki/` entry naming issue #2997 and its PR, recording the decision text. (proven: `docs/changes.d/2026-11-21-stalled-run-cancel-2997.md` + `agent-wiki/2026-11-21-stalled-run-cancel-2997.md`; `make check-docs` rc=0)

## 5. Gates

- [x] 5.1 `make openspec-validate NAME=stalled-run-cancel-policy-2997` rc=0 and `make lane-preflight` rc=0 at the pushed head. (proven: `make openspec-validate NAME=stalled-run-cancel-policy-2997` rc=0; `make lane-preflight` rc=0 before push)
