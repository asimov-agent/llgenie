# auto-merge recheck sweeps a green head whose deferral marker is stale-by-move (#1910)

The `auto-merge` scheduled recheck only re-evaluated a PR whose deferral marker names its
CURRENT head (one marker per head, issue #545). A green head that moved after the last
deferral therefore had no marker for its new head, so the recheck printed "not a retry" and
skipped it forever — and if no `workflow_run` CI completion happened to fire at that head
(main-tip churn saturated the `auto-merge-success` concurrency group), nothing in the fleet
would ever evaluate it.

Measured live on #1817: head `41e522e4` finished CI green at 02:42 while #1804/#1896
merged 02:41–02:43, so no auto-merge `workflow_run` with that `head_sha` was ever created,
and every deferral marker on the PR named an older head. It merged 03:27 by a *subsequent*
main-tip `workflow_run` (run `42334065781`) — luck of a later CI completion, not the recheck.

## Change

`scripts/auto_merge.py::recheck` now also sweeps a PR that carries ANY deferral marker (an
older head) when its CURRENT head is green — no red check and a concluded green run — treating
it as a retry of the same decision. `has_any_deferral_marker()` detects the backlog; the head
must still pass `failing_checks` and `no_concluded_green`, so a RED current head is never
approved or merged on a stale marker. One-comment-per-head dedupe is unchanged: if the decision
still defers, a fresh marker is posted for the new head so the next cron keeps it visible.

## Proof

`tests/test_auto_merge.py`: added `test_a_stale_marker_green_head_is_retried_and_merged`
(merged by the sweep, no `--admin`) and `test_a_stale_marker_red_head_is_not_retried` (red
current head deferred, never approved/merged). Mutation-proved: with the fix removed the green
test fails with the pre-fix "not a retry" skip; with the fix it passes. Full suite: 92 passed.
It is this lane's own pipeline defect (owner 2026-11-01), fixed as a ready-for-review PR.
