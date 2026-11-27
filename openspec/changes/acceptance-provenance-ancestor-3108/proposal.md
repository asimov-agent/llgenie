# Change: head-stable acceptance provenance (#3108)

## Why

`check_pr_acceptance` (mk/gates.mk:145, #2288) reds a ticked criterion whose
`(proven: …)` marker names a head other than the head it measures. PR #3105 was
red-flagged three times in one session (`5f5c720fa389` → `4577eb998d71` →
`ed0fc689b20e`) because the #3096 ticks were proven at `4577eb99` and no lane
re-ticked them in the same push. The verdict and ticks were real; only the head
reference was stale. Each lane "fixed" the mismatch at its own head and the next
push reddened again. This is a provenance-resolution defect, not a grype-pin defect.

## What Changes

- Resolve a ticked criterion's `(proven: …)` head reference against the measured
  `--rev` using the same merge-ancestor rule the repo already uses elsewhere:
  an exact head match passes; a cited head that is an **ancestor** of the measured
  head also passes; an unrelated head, a descendant, a missing object, or an
  ambiguous/unresolvable reference still produces the blocking
  `tick-stale-head-unflagged` finding.
- Apply the resolution to BOTH stale-head paths in `scripts/check_pr_acceptance.py`:
  the run-cited path (green run head / named heads) and the command+`rc`+`sha`
  path with no `run=`.
- Keep the live-run conclusion check intact: a tick citing a red/unreadable run
  still reds (#2288). No gate is skipped, weakened or deleted.
- Add regression tests: ancestor proof clean; unrelated sibling proof blocking;
  missing/unresolvable object still blocking.
- Add the #1123 note/index row trio; no gate/workflow behaviour change beyond
  provenance resolution.

## Benefit

A legitimate rebase/push no longer invalidates a reviewer's verdict-backed tick,
while a proof from an unrelated commit still holds the close. The audit trail
still names the sha it was measured at.

## Not covered

- The grype pin itself (#3096) and its digest — untouched.
- No merge, no arm, no self-tick (#1088/#1644).
