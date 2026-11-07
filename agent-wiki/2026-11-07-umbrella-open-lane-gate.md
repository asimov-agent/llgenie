# Umbrella open-lane close gate (#1859)

The #1815/#1816 squash-text acceptance gate holds a close when the linked umbrella's OWN
`## Acceptance criteria` are unticked. It never read a second issue, so a close that fires on an
umbrella whose own boxes are all ticked — but whose rollout LANE issues are still open — passed
GREEN. Measured on #1849's fleet: every lane issue (#1850/#1853/#1855/#1856/#1851) carries the
umbrella's number back, while incidental umbrella-body refs (#1791/#1792/#1724/#791) never do —
the bidirectional citation is the deterministic lane signal. #1849's recurrence (#1856's squash
auto-closed it at 1/5 lanes) is the class this half exists to stop once the boxes are ticked.

## What changed

`scripts/check_pr_acceptance.py` now, beside `acceptance_verdict` on the linked issue, runs
`rollout_lane_findings`: it derives the umbrella's candidate lanes from the umbrella's OWN live
body citations (`#<n>`), probes each referenced issue's live body + state, and emits a
`rollout-lane-open` finding for any referenced issue that is still OPEN and cites the umbrella
back. A referenced-open issue that does NOT cite the umbrella back (process context) or that is
CLOSED is not a lane and never holds; an unreadable reference never holds (a data gap is not a
provable open lane). The lane set is derived at merge time, never a hand-kept roster (#301).

Tests (red-on-old/green-on-fixed): an OPEN lane that cites the umbrella back holds a
fully-ticked umbrella close; an open non-citing reference does not hold; a CLOSED lane does not
hold; a no-lane umbrella stays green. `make check-pr-acceptance` is still verification-only, never
a tick (#1644).

## References

- Issue #1859 (ci-pipelines), the recurrences #1815/#1812/#1849.
- `scripts/check_pr_acceptance.py` `rollout_lane_findings` + `_fetch_issue_meta`.

## Verification

- `make openspec-validate NAME=umbrella-open-lane-gate` exits 0.
- `tests/test_check_pr_acceptance.py` + `tests/test_check_pr_closing.py`: 74 passed (7 added).
- Prove-guard: `test_open_rollout_lane_that_cites_the_umbrella_back_is_RED` fails on the pre-fix
  tree (RED), passes post-fix.
