# Name AND clear permanently stalled `in_progress` runs — the cancel policy issue #2992 deferred (issue #2997)

## Why

The stalled-job watchdog (issue #2992, landed by PR #2992) names a run whose job idles past its
budget while the run is still live. Measured: run `44863652918` (auto-merge's trigger CI for PR #2990
head `8d4892e6797238fae9300fdedf26e138734d575b`) held `linux/unit` (job `136722618230`) `in_progress`
from 03:57:56Z with `updated_at` frozen at 03:57:57Z until 04:23:54Z — every other job concluded in
~1 min. Because the run never reached a conclusion, `ci-verdict` (a `workflow_run` on completion)
never judged that head and `auto-merge.yml` never armed the merge: a ~1 min trigger-CI idling 26
minutes SILENCED the whole merge chain. Naming the stall (the watchdog) is detection, not remedy —
issue #2992 explicitly left cancel policy to this issue. Today nothing clears such a run except a
human or the run eventually concluding; the wedge window is unbounded.

## What Changes

- The stalled-job watchdog gains `--cancel-stalled`: a CANCELLATION POLICY for the class it already
  classifies, modelled on the landed `--cancel-stranded` precedent from the zero-job lane (#1410).
  The DECISION (issue #2997 AC1): cancels are ALLOWED, gated by four proofs evaluated at cancel time —
  1. the run is still the watchdog's own stalled classification (a concluded sibling job + an
     `in_progress` job past the named budget) — no new threshold, no new class;
  2. a live re-read immediately before cancelling: if the stalled job has since concluded or the run
     has concluded, the cancel is SKIPPED and named skipped (the #1822/#1823 rule — a live job is
     never touched);
  3. only PR-head runs on an OPEN, non-draft PR are cancellable; a run with no PR (push/schedule/
     main) is named only — cancelling main-lane runs stays the frozen-reaper/zero-job lanes' domain;
  4. a cancel that races a conclusion ("...is completed") is benign, reported as a race, never a
     delivery failure (the #1410 precedent).
- Cancel is NOT queue-pumping and stays compatible with the AGENTS.md queue-pumping ban: a cancel
  ENDS a run; it never starts one. The watchdog never dispatches, never reruns, and posts nothing
  that triggers a new pipeline. Recovery after a cancel comes from GitHub events (a push, a PR
  synchronize, a label) or a human — exactly the principals the discipline already allows.
- `ci-verdict` and `auto_merge` read a run cancelled-at-head through the already-landed named paths:
  `ci_verdict.BLOCKING_CONCLUSIONS` includes `cancelled` (#1250 Finding B — a cancelled run is a
  killed CI, the verdict posts neutral at that head), and `auto_merge.RED_CONCLUSIONS` defers the
  merge on it. This change pins THAT policy's shape with tests: a watchdog-cancelled head gets a
  CLASSIFIED verdict instead of silence, and the merge sweep names why it defers.
- `.github/workflows/zero-job-pending.yml` carries the action: the watchdog step gains a `CANCEL`
  knob (Makefile-reference style) so the lane that names the stall can also clear it, on the same
  scheduled trigger — no new lane, no new clock.
- `agent-wiki/` + `docs/changes.d/` record the decision and the shape.

## Out of scope

- Cancelling runs on `main` lanes or runs with no PR (named only).
- Any rerun/dispatch/requeue after a cancel — forbidden by the CI pipeline discipline.
