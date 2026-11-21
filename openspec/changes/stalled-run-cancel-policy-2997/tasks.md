# Tasks: stalled-run-cancel-policy-2997

## 1. Change and decision

- [x] 1.1 Open the OpenSpec change (proposal, spec delta, tasks) referencing issue #2997 and its measured run `44863652918` / job `136722618230`, stating the DECISION (cancels allowed under four named proofs; cancel is not queue-pumping) in `Why`/`What Changes`. (proven: `make openspec-validate NAME=stalled-run-cancel-policy-2997` rc=0)
- [ ] 1.2 Record the same decision in the issue #2997 body (AC1) so the issue, the change, and the code agree.

## 2. Implementation (lands on top of the watchdog from PR #2992; rebase onto main once #2992 lands)

- [ ] 2.1 `scripts/stalled_job_watchdog.py`: add `--cancel-stalled` — cancel BEFORE filing (so the comment states the real outcome), live re-read before each cancel (skip when the stalled job concluded), PR-head-only gate (OPEN non-draft PR), benign-race handling, `cancelled/skipped/race` outcome vocabulary.
- [ ] 2.2 `make check-stalled-jobs` gains the `CANCEL=1` -> `--cancel-stalled` knob by reference in mk/bots.mk; `.github/workflows/zero-job-pending.yml` passes it through the existing watchdog step (no new lane, no new clock).
- [ ] 2.3 Pin the classified-verdict path with tests: a watchdog-cancelled PR head read by `ci_verdict` (cancelled in BLOCKING_CONCLUSIONS -> neutral verdict at the head) and by `auto_merge` (cancelled in RED_CONCLUSIONS -> deferral naming the conclusion).

## 3. Tests (`tests/test_stalled_job_watchdog.py` extended, `gh` stubbed on PATH)

- [ ] 3.1 AC2: a stalled run with `--cancel-stalled` is cancelled before filing; the filed comment names the cancel outcome.
- [ ] 3.2 A job that concluded between classification and cancel -> cancel SKIPPED, named skipped; no cancel invoked.
- [ ] 3.3 A cancel racing a conclusion -> reported benign race, exit code unchanged.
- [ ] 3.4 No-PR run (schedule/push) -> named only, never cancelled; draft or closed PR head -> never cancelled.
- [ ] 3.5 No `rerun`/`dispatch`/re-trigger is ever invoked by the cancel path (negative control on the stubbed `gh`).

## 4. Docs

- [ ] 4.1 `docs/changes.d/` fragment + `agent-wiki/` entry naming issue #2997 and its PR, recording the decision text.

## 5. Gates

- [ ] 5.1 `make openspec-validate NAME=stalled-run-cancel-policy-2997` rc=0 and `make lane-preflight` rc=0 at the pushed head.
