## ADDED Requirements

### Requirement: A top-tier dry run outlives one Hub window

The CI process that runs `llgenie --download-top-tier --dry` and the CI process
that runs `llgenie --download-top-tier --family qwen --count 1 --dry` MUST use
`scripts/hf_auth.py` `TOP_TIER_DRY_RUN_TIMEOUT`.

That value MUST be `RATE_LIMIT_WAIT_CAP + 180` seconds. `RATE_LIMIT_WAIT_CAP` is
600, so the process budget is 780 seconds: one capped 429 sleep, then the 180
seconds the detailed dry run already had for discovery.

#### Scenario: the budget is one capped window plus discovery

- **Given** `RATE_LIMIT_WAIT_CAP` is 600 seconds
- **When** the dry-run budget is read
- **Then** `TOP_TIER_DRY_RUN_TIMEOUT` is 780 seconds
- **Test:** `tests/test_hf_auth.py::test_top_tier_dry_run_budget_is_one_window_plus_discovery`

#### Scenario: both dry-run subprocesses use that budget

- **Given** the detailed dry run and the family dry run
- **When** each starts the real launcher
- **Then** the `subprocess.run` timeout is `TOP_TIER_DRY_RUN_TIMEOUT`
- **Test:** `tests/test_hf_auth.py::test_hub_launcher_processes_use_the_dry_run_budget`

#### Scenario: every other Hub launcher subprocess uses that same budget

- **Given** a test subprocess that runs `llama_serve.py` or `hf_download.py` against the Hub
- **When** its `subprocess.run` timeout is a number
- **Then** that number is at least `TOP_TIER_DRY_RUN_TIMEOUT`
- **And** a local-file picker that never calls the Hub may stay shorter
- **Test:** `tests/test_hf_auth.py::test_hub_launcher_processes_use_the_dry_run_budget`

### Requirement: A real 429 is waited out against a local server

`_hf_get` MUST wait `rate_limit_wait` on HTTP 429 and then return the JSON body
of the next successful GET. A test of that behavior MUST run `_hf_get` and
MUST NOT replace `_hf_get`, `rate_limit_wait`, or `time.sleep`. The only
stand-in is the HTTP server.

#### Scenario: one short 429 then a JSON body

- **Given** a local HTTP server whose first response is 429 with `RateLimit` `t=1` and whose second response is 200 JSON
- **When** `_hf_get` requests that URL
- **Then** the call returns that JSON
- **And** the second request arrives at least one second after the first
- **Test:** `tests/test_llama_ai.py::test_hf_get_waits_out_a_local_429`
