# auto-merge-recheck-stale-head

## ADDED Requirements

### Requirement: the recheck sweeps a green head whose deferral markers all name older heads

The recheck sweep MUST re-evaluate a PR that carries a deferral marker for ANY head when its
CURRENT head is green — no red check and a concluded successful run — even if no marker names
the current head because the head moved after the last deferral. A green head stranded by
main-tip churn (the `auto-merge-success` concurrency group saturated, so no `workflow_run`
ever fired at it) MUST NOT be skipped forever as "not a retry"; it IS the merger's own backlog
and the same decision MUST run against the current tree. One-comment-per-head dedupe is
unchanged: if the decision still defers, a fresh marker for the new head is posted so the next
cron keeps it visible.

WHEN the sweep lists an open PR whose thread carries a deferral marker for an OLDER head and
whose current head has no red check and a concluded green success run
THEN it evaluates (and merges if green + CLEAN, exactly as a would-be-first-time decision would).

#### Scenario: a stale-by-move green head is merged by the recheck

- **Given** a PR whose every deferral marker names older heads, whose current head is green
  (`mergeStateStatus: CLEAN`, no red check, a concluded-success run)
- **When** the recheck sweep runs
- **Then** the current head is evaluated and the PR is merged through the one decision, never
  `--admin`, and never skipped as "not a retry"
- **Test:** `tests/test_auto_merge.py::test_a_stale_marker_green_head_is_retried_and_merged`

### Requirement: a red current head is still refused on a stale marker

A PR whose CURRENT head has a red check MUST NOT be approved or merged because an older deferral
marker exists — the recheck retains the #1386 rule (a red pipeline is never merged) for this
path too. The stale marker proves the PR was deferred before; it does not clear the current
tree's own red verdict.

WHEN the sweep lists a PR with a stale deferral marker whose current head has a red check
THEN it defers with the red reason and never posts an approval or a merge.

#### Scenario: a stale marker does not clear a red current head

- **Given** a PR with a deferral marker for an old head, whose CURRENT head has a failed `scope`
  check (the #1401 head), `mergeStateStatus: BLOCKED`, `reviewDecision: REVIEW_REQUIRED`
- **When** the recheck sweep runs
- **Then** it defers naming the red run, and no `pr review` or `pr merge` is issued
- **Test:** `tests/test_auto_merge.py::test_a_stale_marker_red_head_is_not_retried`

### Requirement: the sweep's scope does not widen to every open PR

A PR with NO deferral marker at all MUST remain untouched by the recheck — the sweep retries the
gate's OWN deferrals, not every green open PR (a never-deferred PR is picked up by its own CI
completion's `workflow_run`). `has_any_deferral_marker` is the gate that keeps the sweep bounded;
the one-comment-per-head dedupe and the `max_prs` cap are unchanged.

WHEN the sweep lists an open PR with no deferral marker for any head
THEN it prints "not a retry" and neither evaluates nor merges it.

#### Scenario: a never-deferred PR is untouched

- **Given** an open PR with no deferral marker in its thread
- **When** the recheck sweep runs
- **Then** it is not evaluated and nothing is merged
- **Test:** `tests/test_auto_merge.py::test_a_pr_without_a_deferral_marker_is_not_touched`
