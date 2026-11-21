# 2026-11-21 — stalled-run cancel policy (issue #2997)

## What was verified against the spec

Issue #2997 is the cancel policy issue #2992 explicitly deferred: the stalled-job
watchdog (`scripts/stalled_job_watchdog.py`, landed via PR #2998) NAMES runs whose
jobs instantiated but where one job hangs `in_progress` while its siblings concluded
(measured wedge: run `44863652918`, job `136722618230`, 26 min on `linux/unit`) —
it never cleared them.

Implemented per the OpenSpec change `stalled-run-cancel-policy-2997`:

- `--cancel-stalled` (Makefile knob `CANCEL=1` on `make check-stalled-jobs`) cancels
  each classified stalled run via `gh run cancel <id> --repo <repo> --force`, gated
  by the four proofs the issue names, all evaluated AT CANCEL TIME:
  1. the cancel reuses the watchdog's own classification — no new threshold, no new class;
  2. a LIVE re-read (`gh run view --json status,jobs`) immediately before the cancel;
     a stalled job that concluded between classification and cancel, a run that
     concluded, a re-read that fails, or a job back under budget all SKIP the cancel
     (the #1822/#1823 rule: a live job is never touched; no cancel on stale data);
  3. only heads carrying an OPEN, NON-DRAFT pull request are cancellable — no-PR
     (push/schedule/main) runs, draft heads, and closed-PR heads are named only,
     staying the zero-job (#1410) / frozen-reaper lanes' domain;
  4. a cancel that races a conclusion (`gh` answers "…is completed") is a benign race
     with exit unchanged — the #1410 `--cancel-stranded` precedent, not a delivery failure.
- Cancel BEFORE filing: the one deduped PR comment states the outcome that actually
  happened (`CANCELLED` / `cancel SKIPPED — <why>` / benign race), never a claim the
  watchdog didn't earn.
- Queue-pumping stays forbidden: the cancel ENDS a run and the watchdog invokes
  nothing that starts one (negative-control test asserts no `rerun`/`dispatch`/
  re-trigger/`pr merge` call in the whole cancel-path call journal).
- Classified-read pins (AC2): `cancelled` is in `ci_verdict.BLOCKING_CONCLUSIONS` and
  `auto_merge.RED_CONCLUSIONS` (equality already pinned by
  `test_the_blocking_conclusions_are_the_merger_s_rule`, #1250 Finding B); a new
  `tests/test_ci_verdict.py` test pins the post-cancel fan-out shape — the selected
  `linux/unit cancelled` row is accounted as unjudged, never `skipped_by_decision`:
  a classified answer, not the 26-minute silence #2992 measured.
- `zero-job-pending.yml`'s watchdog step now runs `make check-stalled-jobs FILE=1
  CANCEL=1`; the lane header's Never-line was reworded to match the policy (still
  never a cancel of an unclassified run, no-PR/draft head, or any rerun/dispatch).

## Key decisions

- Rebase onto main after #2998 landed so the cancel lives in the SAME script as the
  classification it reuses — the proof-1 gate is literally the watchdog's own
  `stalled_runs()` finding re-validated on a fresh read, not a second detector.
- The cancel is a knob, not a default: `CANCEL=1`/`--cancel-stalled` off means the
  script names only, exactly as shipped in #2992 — the negative tests keep the old
  behaviour pinned.
- Closed-PR heads are named (the marker still lands where a reader looks) but never
  cancelled — proof 3 is about who owns clearing a run, not about visibility.

## Current status

Detector unchanged (7 #2992 tests green); 5 cancel-policy tests + 1 verdict pin green
locally. PR pending; CI arms the lane step with `CANCEL=1` from the merge onward.
