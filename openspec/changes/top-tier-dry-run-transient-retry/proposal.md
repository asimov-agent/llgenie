# fix(ci): a top-tier dry run survives one transient Hub failure

Issue: [#399](https://github.com/asimov-agent/llgenie/issues/399)

## Why

`macos / top-tier` and `linux / top-tier` run `make ci-top-tier`
(`.github/workflows/pipeline.yml`, the `top-tier` job), and that target runs the
`--download-top-tier --dry` acceptance cases, whose only non-hermetic step is a live
Hugging Face read. When that read is slow the dry run exits 1 and the PR-blocking job
goes red on a diff that has nothing to do with it. Measured on the same tree (run
39381961586, #396 rebased): `macos / top-tier` failed with
`TimeoutError: The read operation timed out` at
`tests/test_top_tier_acceptance.py:454`, and its unchanged re-run passed; `linux /
top-tier` passed. A reviewer learns the diff is fine only by re-running.

`scripts/llgenie_serve.py::_hf_get` now retries a read-phase `TimeoutError` inside the
process (#549, merged `333344c`). That bounds ONE read. When the in-process budget is
spent the subprocess still exits 1, so the job's conclusion still rests on the Hub's
behaviour during a single run. The issue's "What done looks like" asks for the
bounded-retry seam to be used by these acceptance cases.

## What Changes

- `tests/top_tier_dry_run.py` (new) — `run_dry_run()`, the seam the `--dry` acceptance
  cases shell out through. It retries the whole dry run `TOP_TIER_DRY_RUN_ATTEMPTS` (2:
  the run plus ONE retry), and retries ONLY a Hub transport failure, classified from the
  child's own stderr (`[ERROR] HF API still failing after N attempts`, `TimeoutError`,
  `URLError`, transient HTTP statuses, ...). Any other failure is returned on the first
  attempt, so a real regression is never retried into a green.
- `tests/test_top_tier_acceptance.py` — both dry-run cases
  (`test_cli_download_top_tier_dry_run_detailed`,
  `test_family_dry_run_known_lowend_one_provider`) run through the seam, and their
  assertion names the attempt count and the cause.
- `tests/test_top_tier_dry_run_retry.py` (new) — real child processes (no mocked
  `subprocess`, no mocked transport): a transient failure then success is retried once
  and the retry's result returned; an always-failing Hub spends the bound and still
  returns a non-zero exit naming the cause; a non-transient failure is not retried; the
  measured `TimeoutError: The read operation timed out` shape is transient and an
  `AssertionError` is not.
- `README.md` — states the dry-run retry bound and that an unreachable Hub still fails
  loudly.
- `agent-wiki/2026-10-23-top-tier-dry-run-transient-retry.md` — the work record.

## Impact

- Affected specs: `top-tier-dry-run-transient-retry` (new capability).
- Affected code: `tests/top_tier_dry_run.py` (new),
  `tests/test_top_tier_acceptance.py`, `tests/test_top_tier_dry_run_retry.py` (new),
  `README.md`, `agent-wiki/`.
- No product code changes: `scripts/llgenie_serve.py` keeps #549's in-process retry.
- No test is skipped and no assertion is weakened: the acceptance cases still assert a
  zero exit and every row/readout they asserted before; only the number of attempts is
  bounded and stated.

## Not covered (each its own issue)

- The live read stays on the PR-blocking path: this change bounds it (retry) rather than
  moving it to a scheduled job, which is the issue's other permitted option and a
  materially different change.
- `test-top-tier-serve-ci`'s real model download on the same job is a different
  live-network dependency and is untouched here.
