# fix(ci): top-tier dry runs outlive one Hub rate-limit window

Issue: [#180](https://github.com/asimov-agent/llgenie/issues/180)

## Why

`rate_limit_wait` already sleeps until the Hub window resets, up to 10 minutes.
The CI dry runs kill the process during that sleep. `test_cli_download_top_tier_dry_run_detailed`
allows 180 seconds (pull request #174 died at `retrying in 236.0s`).
`test_family_dry_run_known_lowend_one_provider` allows 300 seconds (pull request #175
died at `retrying in 266.0s`, pull request #176 at `retrying in 278.0s`).

A process limit equal to the 600-second cap still expires as a full sleep ends,
before the retry can finish the listing. The budget is the cap plus the 180
seconds the detailed dry run already had for discovery.

## What Changes

- `scripts/hf_auth.py` defines `TOP_TIER_DRY_RUN_TIMEOUT = RATE_LIMIT_WAIT_CAP + 180`.
- Both CI dry-run subprocesses use that name.
- Every other test subprocess that runs `llama_serve.py` or `hf_download.py` against the Hub uses that same budget. A local-file picker that never calls the Hub keeps its short limit.
- A unit test locks the sum and both call sites.
- A unit test runs the real `_hf_get` against a local HTTP server: 429 with
  `RateLimit: t=1`, then 200 JSON. The gap between the requests is at least one
  second. Nothing replaces `_hf_get`, `rate_limit_wait`, or `time.sleep`.
- README states the CI dry-run budget.

## Impact

- `scripts/hf_auth.py`
- `tests/test_top_tier_acceptance.py`
- `tests/test_hf_auth.py`
- `tests/test_llama_ai.py`
- `README.md`

Not this change: the TensorFold detect false-positive on pull request #175,
issue #178, issue #179.
