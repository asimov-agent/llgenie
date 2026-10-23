# top-tier-dry-run-transient-retry

## ADDED Requirements

### Requirement: a transient Hub failure retries the dry run within a stated bound

The `--download-top-tier --dry` acceptance cases that run inside the PR-blocking
`top-tier` job MUST run through `tests/top_tier_dry_run.py::run_dry_run`, which retries
the whole dry run `TOP_TIER_DRY_RUN_ATTEMPTS` (2) times — the run plus ONE retry — so a
PR's `macos / top-tier` and `linux / top-tier` conclusion does not rest on one live Hub
read at one moment.

WHEN a dry run exits non-zero because the Hub's transport failed
THEN the seam retries it once and returns the retry's result.

#### Scenario: a transient dry-run failure is retried and the retry passes

- **Given** a real child process that exits 1 once with the CLI's exhausted-budget line
  `[ERROR] HF API still failing after 8 attempts ...` and exits 0 on its next run
- **When** `run_dry_run` runs it
- **Then** it returns the zero exit and reports 2 attempts used
- **And** the child really ran twice
- **Test:** `tests/test_top_tier_dry_run_retry.py::test_transient_failure_is_retried_once_and_the_retry_passes`

#### Scenario: both dry-run acceptance cases shell out through the seam

- **Given** `tests/test_top_tier_acceptance.py`
- **When** its `test_cli_download_top_tier_dry_run_detailed` and
  `test_family_dry_run_known_lowend_one_provider` cases run the real CLI
- **Then** each runs through `run_dry_run` with `TOP_TIER_DRY_RUN_TIMEOUT` as the process
  budget, and its zero-exit assertion names the attempt count and the CLI's cause
- **Test:** `tests/test_top_tier_acceptance.py::test_cli_download_top_tier_dry_run_detailed`
  and `tests/test_top_tier_acceptance.py::test_family_dry_run_known_lowend_one_provider`
  (live proof, CI jobs `top-tier` -> `make ci-top-tier`; the seam itself is
  `tests/test_top_tier_dry_run_retry.py`)

### Requirement: an unreachable Hub still fails loudly at the bound

A dry run whose Hub read fails on every attempt MUST spend the stated bound and then
return a NON-ZERO exit carrying the CLI's named cause. It MUST NOT become a skip, a soft
pass, or a green.

WHEN every attempt fails on the Hub's transport
THEN the bound is spent and the non-zero exit is returned, never a skip.

#### Scenario: a Hub that stays unreachable spends the bound and stays red

- **Given** a real child process that exits 1 with `[ERROR] HF API still failing after 8
  attempts ...` on every run
- **When** `run_dry_run` runs it
- **Then** it reports exactly `TOP_TIER_DRY_RUN_ATTEMPTS` attempts and a non-zero exit
- **And** the returned stderr names `HF API still failing after`, so the caller's
  assertion fails with the cause
- **Test:** `tests/test_top_tier_dry_run_retry.py::test_a_hub_that_stays_unreachable_fails_loudly_at_the_bound`

### Requirement: a failure that is not the Hub's transport is never retried

`run_dry_run` MUST return a non-transient failure on the first attempt, so a bug or a bad
argument is never retried into a green. Only the Hub's transport classes are retryable:
`[ERROR] HF API still failing after N attempts`, `TimeoutError`, `URLError`, connection
resets/errors, `SSLError`, resolution failures, and the transient HTTP statuses
(429/502/503/504).

WHEN a dry run fails for a reason that is not the Hub's transport
THEN it is returned at once, with no retry.

#### Scenario: a wrong argument is not retried

- **Given** a real child process that exits 2 with `ValueError: bad --count argument`
- **When** `run_dry_run` runs it
- **Then** it reports 1 attempt and the non-zero exit
- **Test:** `tests/test_top_tier_dry_run_retry.py::test_a_non_transient_failure_is_never_retried`

#### Scenario: the measured read-timeout shape is retryable, an assertion is not

- **Given** a failed child whose stderr carries `TimeoutError: The read operation timed
  out` (the measured shape of run 39381961586), and another carrying
  `AssertionError: candidate row must show tier folder`
- **When** the seam classifies each
- **Then** the read timeout is transient and the assertion is not
- **Test:** `tests/test_top_tier_dry_run_retry.py::test_transient_classification`

## Notes

- No product code is touched: `scripts/llgenie_serve.py::_hf_get` keeps #549's
  in-process retry of a read-phase `TimeoutError`; this change bounds the process-level
  retry the acceptance cases needed, which is the issue's first permitted mechanism.
