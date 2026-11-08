## ADDED Requirements

### Requirement: a mid-flight deferral re-decides itself instead of waiting for an event

When the merge gate defers a head because one of its workflow runs is still `in_progress`, the sweep
SHALL wait a bounded time for that run to conclude and re-ask the verdict, merging the head in the
same run when it concludes green. It SHALL NOT depend on a later CI completion or a scheduled sweep.

A green head produces no further CI completion, and the scheduled recheck fires ~4–5×/day even
though its cron declares 48 (issue #2101, measured 2026-11-08). The deferral therefore deferred to
an event that never arrives: `#2069` at `cc72588c` was 16/16 green, armed, deferred under #1551, and
then lost its green tree to a rebase.

#### Scenario: a run that concludes green is merged in the same sweep

- **GIVEN** a green, mergeable head whose run row is `in_progress` on the first read
- **AND** that row reports `completed`/`success` on the next read
- **WHEN** the sweep decides the head
- **THEN** the head is merged within the same invocation, with no further CI completion
- **Test:** `tests/test_auto_merge.py::test_run_itself_waits_for_an_unfinished_row_and_then_merges`

#### Scenario: a genuinely unfinished head is still never merged

- **GIVEN** a head whose run stays unfinished for the whole bound
- **WHEN** the sweep decides the head
- **THEN** it still defers under #1551 and merges nothing
- **Test:** `tests/test_auto_merge.py::test_an_unfinished_row_that_concludes_green_is_merged_in_the_same_run`
  (the negative half) and the existing #1551 suite

### Requirement: the recheck decides any concluded-green head, marker or not

The recheck SHALL evaluate any open PR whose current head has a concluded green run and no red
check, whether or not it carries an auto-merge deferral marker, because a cancelled sweep posts no
marker. It SHALL still refuse a head with a red check or with no concluded green run.

The concurrency group cancels 41% of sweeps (measured: `success=59, cancelled=41` of the last 100),
so a marker-only net is blind to exactly the PR population that cancellation produces.

#### Scenario: a markerless concluded-green head is merged

- **GIVEN** an open PR with no deferral marker whose head concluded green
- **WHEN** the recheck runs
- **THEN** the head is decided and merged
- **Test:** `tests/test_auto_merge.py::test_a_markerless_concluded_green_head_is_merged`

#### Scenario: a markerless red head is refused

- **GIVEN** an open PR with no deferral marker whose head carries a failing check
- **WHEN** the recheck runs
- **THEN** nothing is merged
- **Test:** `tests/test_auto_merge.py::test_a_markerless_red_head_is_still_refused`

#### Scenario: a markerless head with no concluded green run is refused

- **GIVEN** an open PR with no deferral marker whose only run is still `in_progress`
- **WHEN** the recheck runs
- **THEN** nothing is merged
- **Test:** `tests/test_auto_merge.py::test_a_pr_without_a_deferral_marker_and_no_concluded_green_run_is_not_touched`

### Requirement: the recheck covers every open PR, not a fixed five

The recheck's default cap SHALL cover the open board so no PR is permanently starved by the cap.

Twelve PRs were open against `--max-prs 5` (issue #2101), so seven were never evaluated. The sweep
is idempotent — it re-reads live state and each merge is one atomic call — so a higher bound costs
reads, not merges.

#### Scenario: twelve open green PRs are all evaluated

- **GIVEN** twelve open PRs, each a concluded-green head with no deferral marker
- **WHEN** the recheck runs at its default cap
- **THEN** all twelve are evaluated
- **Test:** `tests/test_auto_merge.py::test_the_recheck_covers_every_open_pr_not_just_five`

### Requirement: the workflow documents the measured schedule rate, never a claimed one

The merge workflow SHALL state the rate the schedule actually achieves and SHALL NOT justify
`cancel-in-progress: true` with a safety net that does not fire at that rate.

#### Scenario: the file carries the measurement

- **GIVEN** `.github/workflows/auto-merge.yml`
- **WHEN** its schedule and concurrency comments are read
- **THEN** they name the measured per-day rate, the zero-cancellation fact and the zero queue lag,
  and they no longer claim 30-minute coverage
- **Test:** `tests/test_auto_merge.py` (workflow text assertions) and review of the file

### Requirement: the rebase sweep never discards an armed, settled-green head

The rebase sweep SHALL NOT rebase a PR whose head is armed for auto-merge (`autoMergeRequest`
present) AND settled green (no check in flight, no red check). It SHALL record the mergeability
answer it measured for that head before passing it over.

A force-push destroys the verified tree the merger was about to land: `#2069` at `cc72588c` was
armed, 16/16 checks `success`, and was force-pushed to `fbbc29a6` at `04:02:38Z`, re-running the
whole matrix (issue #2101). Recovering a missed merge must not cost more CI than the merge would
have, so the recovery path must check mergeability at the head first.

#### Scenario: an armed green head is left to the merger

- **GIVEN** an open PR armed for auto-merge, behind main, with every check green
- **WHEN** the rebase sweep evaluates it
- **THEN** it is passed over with a reason naming the arm state and the measured mergeability
- **Test:** `tests/test_rebase_bot_sweep.py::test_an_armed_green_head_is_not_rebased_out_from_under_the_merger`

#### Scenario: an unarmed or armed-but-red head is still rebased

- **GIVEN** a behind PR that is not armed, or is armed but has a failing check
- **WHEN** the rebase sweep evaluates it
- **THEN** it is still taken for rebase (the guard starves nothing)
- **Test:** `tests/test_rebase_bot_sweep.py::test_an_unarmed_behind_head_is_still_rebased` and
  `::test_an_armed_but_red_head_is_still_available_to_the_rebase`

### Requirement: the retry job is not cancellable by the sweep it retries

The merge workflow SHALL NOT declare `concurrency` at workflow level. The `merge` job SHALL keep its
own superseding group, and the `recheck` job SHALL declare a separate group with
`cancel-in-progress: false`.

A workflow-level concurrency block with `cancel-in-progress: true` cancels the ENTIRE run, including
the `recheck` job — so the cancellation rate (41% of runs, measured) was cancelling the recovery
pass along with the attempt it exists to recover (issue #2101). A retry that dies with the thing it
retries is not a retry.

#### Scenario: a newer sweep supersedes a sweep but never the retry

- **GIVEN** a running sweep with a `recheck` job
- **AND** a newer `CI` completion starts another run
- **WHEN** GitHub applies concurrency
- **THEN** the older `merge` job may be superseded, and the `recheck` job is not cancelled
- **Test:** `tests/test_auto_merge.py::test_the_workflow_has_no_top_level_concurrency_block` and
  `::test_the_recheck_job_is_never_cancelled_by_a_newer_sweep`
