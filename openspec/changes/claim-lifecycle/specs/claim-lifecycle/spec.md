# claim-lifecycle

## ADDED Requirements

### Requirement: a claim marker carries the terms its reader applies

The claim marker MUST carry the window the writer asks for (`ttl=<minutes>m`) and, when the writer
knows it, the run holding the claim (`run=<id>`). A reader MUST age a claim by the TTL its marker
announced and use its own value only as the fallback for a marker without one. The sentence a human
reads MUST be built from the same TTL, so the prose and the mechanism cannot disagree.

WHEN a bot claims a subject with a window shorter than a reader's default
THEN the reader's default does not extend it.

#### Scenario: a thirty-minute claim does not hold for four hours

- **Given** a rebase claim announcing `ttl=30m`, ninety minutes old
- **When** the fix-bot's sweep reads it with its own four-hour default
- **Then** the claim holds nothing, and the reason names the claim's own window
- **Test:** `tests/test_bot_claims.py::test_a_short_claim_does_not_block_a_reader_that_would_age_it_for_hours`

#### Scenario: a legacy marker falls back to the reader's TTL

- **Given** a marker with no `ttl=`/`run=` (written before this change)
- **When** a reader ages it
- **Then** the reader's own TTL decides, and no liveness check is attempted
- **Test:** `tests/test_bot_claims.py::test_a_legacy_marker_falls_back_to_the_readers_ttl`

### Requirement: a claim whose run is over releases the subject, loudly

A reader that can ask GitHub MUST release a claim whose run is no longer running (finished,
cancelled, killed), MUST say so, and MUST NOT release a claim whose run state could not be
determined — an unreadable probe is not evidence that the holder is gone.

WHEN a run is cancelled with its claim still on the subject
THEN the next bot takes the subject instead of waiting for the TTL, and names the dead run.

#### Scenario: a cancelled run frees its PR, and an unknown probe does not

- **Given** a claim carrying `run=424242`
- **When** the probe says the run is over
- **Then** the subject is free and `released()` names the run
- **And** a probe returning `None` (unknown) leaves the claim holding
- **Test:** `tests/test_bot_claims.py::test_a_cancelled_run_releases_its_claim_and_says_so` and
  `tests/test_bot_claims.py::test_an_unknown_run_state_never_releases_a_claim`

### Requirement: every writer states its terms and the pickers report a takeover

All four bots MUST claim with their own `ttl` and their `GITHUB_RUN_ID`, and every picker MUST pass a
cached liveness probe and print `released()` when it takes a subject that had a claim. The release
vocabulary MUST accept a run that stops without finishing (`cancelled`).

WHEN a picker takes a subject whose previous holder is gone
THEN the run log says who held it and why it no longer does.

#### Scenario: the pickers pass the probe and print the takeover

- **Given** the four pickers (`issue_implementer`, `issue_refiner`, `fix_bot_sweep`, `rebase_bot_sweep`)
- **When** their claim reads are inspected
- **Then** each passes `is_live=` and prints `released(...)`, and each writer passes `run_id=`
- **Test:** the per-bot suites (`tests/test_issue_implementer.py`, `tests/test_issue_refiner.py`,
  `tests/test_fix_bot_sweep.py`, `tests/test_rebase_bot_sweep.py`) plus
  `tests/test_bot_claims.py::test_cancelled_is_a_release_word`
