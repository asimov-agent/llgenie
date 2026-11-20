# Spec Delta: sweep-record-2652 (issue #2652)

Capability: `sweep-record`
Issue: [#2652](https://github.com/asimov-agent/llgenie/issues/2652) (rolling tracker —
the implementation PR names it and never closes it)

## ADDED Requirements

### Requirement: the recheck sweep records its decisions on the tracker when asked

`scripts/auto_merge.py recheck` SHALL accept `--record <issue-number>`. When set and
the run is not `--dry`, the sweep SHALL post exactly ONE comment on that issue after
the sweep finishes: first line exactly
`[sweep <UTC-stamp>] merged=<n> approved=<n> deferred=<n>` (UTC stamp
`%Y-%m-%dT%H:%M:%SZ`), then one `#<pr>: <deferral reason>` line for every PR this
sweep deferred in this run. The counts SHALL reflect the decisions this sweep
actually made — merges it landed, approvals it posted, deferral markers it wrote —
not the state of the board it read.

#### Scenario: a recorded sweep posts the fixed-format comment once

- **Given** a stub gh store with two deferred-retry PRs (one re-deferred with a
  reason, one merged) and a record issue 2652
- **When** `recheck(..., record=2652)` finishes a non-dry sweep
- **Then** exactly one comment exists on 2652 whose first line matches
  `^\[sweep \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\] merged=1 approved=0 deferred=1$`
  and the second line names `#<num>:` with the deferral reason
- **Test:** `tests/test_auto_merge.py::test_recheck_record_posts_one_fixed_format_comment`

#### Scenario: a dry sweep never records

- **Given** the same stub store
- **When** `recheck(..., record=2652, dry=True)` finishes
- **Then** no comment was posted on 2652
- **Test:** `tests/test_auto_merge.py::test_recheck_record_dry_posts_nothing`

#### Scenario: without --record the sweep writes nothing to any issue

- **Given** the same stub store and no `record` value
- **When** `recheck(...)` finishes a non-dry sweep
- **Then** no new comment exists on 2652 (the sweep behaves exactly as before)
- **Test:** `tests/test_auto_merge.py::test_recheck_without_record_stays_quiet`

### Requirement: the live sweeper passes the record target

`make auto-merge-recheck` SHALL forward `RECORD=<issue>` to the recheck command, and
the `auto-merge.yml` lane's recheck step SHALL run it with `RECORD=2652`, so every
scheduled sweep records on the rolling tracker without any host-side cron leg.

#### Scenario: the make target and the lane name the tracker

- **Given** the Makefile and `.github/workflows/auto-merge.yml` at this commit
- **When** `make -n auto-merge-recheck REPO=x RECORD=2652` prints the command and
  the workflow's recheck step is read
- **Then** the printed command carries `--record 2652` and the workflow step carries
  `RECORD=2652`
- **Test:** `tests/test_auto_merge.py::test_record_target_is_wired_through_make_and_the_lane`

### Requirement: the tracker is never closed by a sweep-record implementation

An implementation PR for the sweep record SHALL reference #2652 in its `Issue:` line
without any closing keyword; #2652 stays OPEN as the record home.

#### Scenario: the change carries the tracker rule

- **Given** this OpenSpec change
- **When** its proposal and tasks are read
- **Then** the no-close rule is stated and the PR-body construction names #2652
  without a closing keyword
- **Test:** verified by the PR body review step of the landing (body carries
  `Issue: #2652` and no `closes #2652`)
