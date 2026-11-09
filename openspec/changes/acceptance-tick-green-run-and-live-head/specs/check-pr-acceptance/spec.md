# Acceptance-tick evidence must be live-green and current-head (issue #2288)

## ADDED Requirements

### Requirement: a ticked criterion's cited run must conclude live-success

`check-pr-acceptance` re-reads each `run=<id>` a TICKED criterion cites and holds it as
`tick-red-run` when the run's live `gh run view` conclusion is not `success` (a by-design guard-red
run, a failed run, or an unreadable run are all held — never trusted as proof).

#### Scenario: a cited run that concluded failure is held

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion citing `run=<id>`
When the run's live `gh run view` conclusion is `failure` (e.g. the by-design `check-pr-acceptance`
guard red that fires while the box is unchecked)
Then `check-pr-acceptance` reports a `tick-red-run` finding naming the run and its conclusion
And the merge is held (non-zero exit)
- **Test:** `tests/test_check_pr_acceptance.py::test_a_red_cited_run_tick_is_RED_as_tick_red_run`

#### Scenario: a cited run that concluded success is green

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion citing `run=<id>`
When the run's live `gh run view` conclusion is `success`
Then no `tick-red-run` finding is raised
And the read of that criterion stands on the green live run
- **Test:** `tests/test_check_pr_acceptance.py::test_a_successful_cited_run_tick_is_GREEN`

### Requirement: a ticked criterion's cited head must be current

A ticked criterion citing `head=<sha>` (or `live=<sha>`) must name the PR's live head at the
merge-time head; a cited head/live that differs is reported `tick-stale-head` and holds the merge.

#### Scenario: a stale (rebased) head is held

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion citing a `head=<sha>`
or `live=<sha>` that is no longer the PR's merge-time head
When `check-pr-acceptance` runs with the PR's current head as the referee
Then it reports a `tick-stale-head` finding naming the cited head and the current head
And the merge is held (non-zero exit)
- **Test:** `tests/test_check_pr_acceptance.py::test_a_stale_head_tick_is_RED_as_tick_stale_head`

#### Scenario: a current live head twin is green

Given a `- [x]` criterion whose `live=<sha>` twin equals the merge-time head
When `check-pr-acceptance` runs with that same head
Then no `tick-stale-head` finding is raised
- **Test:** `tests/test_check_pr_acceptance.py::test_a_cited_head_matching_the_live_head_is_GREEN`

#### Scenario: a non-sha head argument only skips the staleness referee

Given `--rev HEAD` (a bare word, not a sha) as the merge-time head
When `check-pr-acceptance` re-checks a ticked criterion
Then the staleness referee is skipped (a word cannot be a sha to compare against)
And the run re-check still runs (an unreadable/failed run still holds)
- **Test:** `tests/test_check_pr_acceptance.py::test_live_evidence_is_skipped_when_rev_is_not_a_sha`

### Requirement: the write-back names the live head beside `head=`

`review_finalize` writes a `live=<sha>` twin beside every `head=<sha>` it ticks, so a marker names
both the measured head and the PR's live head at measurement.

#### Scenario: a head-carrying verdict-ref gets its live twin

Given a review-finalize verdict-ref that carries `head=<sha>`
When the write-back runs with a known live head
Then the ticked marker also carries `live=<shalive>`
And re-applying is idempotent (the twin is not duplicated)
- **Test:** `tests/test_review_finalize.py::test_with_live_head_attaches_the_live_head_twin`

## MODIFIED Requirements

### Requirement: `check-pr-acceptance` reports an unchecked-close violation

The existing `acceptance-unchecked` / `acceptance-exceeds` / `tick-unprovable` findings remain, joined
by the two new live-evidence classes (`tick-red-run`, `tick-stale-head`), both blocking.

#### Scenario: all ticked-evidence classes coexist

Given a linked issue with a ticked criterion citing a failed run AND a stale head
When the gate runs with the current head as referee
Then both a `tick-red-run` and a `tick-stale-head` finding are reported
And the merge exits non-zero
