# Change: align the planner SOUL with CI-only landing

## Why

Issue #3084: `agents/llgenie-planner/SOUL.md` still told the planner that "Every merge needs
the owner's approval" and to stop at the reviewable PR. Canonical `AGENTS.md` rule 7 says an
approval is no longer a precondition: CI lands a green, conflict-free PR by itself, and
`REVIEW_REQUIRED` is not a human gate to wait on. A planner that obeys the stale SOUL line
idles while a run is in flight instead of picking up the next un-PR'd board issue. PR #3085
edits that SOUL paragraph, but its guard row `make check-pr-openspec-change` went red because
the diff named no OpenSpec change — this change is the checklist of record it needs.

## What Changes

- The planner SOUL's merge paragraph says what `AGENTS.md` rule 7 actually says: never
  hand-merge, never push to `main`; CI's `auto-merge` job squash-merges when every relevant
  PR job passed and `mergeStateStatus == CLEAN`, with no human click.
- An approval is neither a precondition for landing nor a licence to merge;
  `REVIEW_REQUIRED` is explicitly not a state to wait on.
- While a CI run is in flight the planner takes the next un-PR'd board issue end-to-end
  instead of idling or polling — one lane at a time.
- The change is documented with the required agent-wiki note and one-row changes index
  fragment so `check-docs` sees it.

## Benefit

The planner's own governing document stops contradicting the repository rulebook. Green,
conflict-free PRs land without a human click, and an in-flight CI run no longer stalls the
planner's queue. The guard's OpenSpec-presence row has a real, named change to bind to.

## Not covered

- `AGENTS.md` itself and the auto-merge workflow are unchanged; this change only aligns the
  planner profile's SOUL with the rule already in force (issue #3084).
- No engine pin, engine parameter or workflow trigger is touched by this change.
