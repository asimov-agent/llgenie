## ADDED Requirements

### Requirement: One rate-limit wait, shared by callers and tests

The seconds to wait after a Hub HTTP 429 MUST be computed by one function in `scripts/hf_auth.py`. Every script that GETs the Hub, and every test that asserts that wait, MUST call that function. A caller MUST NOT keep its own 429 pause.

The wait is the `t` value (seconds remaining) from the `RateLimit` header. When that value is absent the wait is 300 seconds. The wait MUST NOT exceed 600 seconds.

A 429 MAY be retried twice (three attempts). A response that is not HTTP 429 MUST reset the consecutive-429 count, so a later 429 gets the full retry budget again. When the budget is spent the call MUST fail.

HTTP 401, 403 and 404 MUST fail on the first attempt. HTTP 5xx and a transport error MUST keep a short backoff and the same attempt budget, and MUST NOT wait for the rate-limit window.

#### Scenario: a 429 waits for the header's reset

- **Given** an HTTP 429 whose headers include `RateLimit: "api";r=0;t=12`
- **When** the shared wait is computed
- **Then** the wait is 12 seconds
- **Test:** `tests/test_hf_auth.py::test_rate_limit_wait_uses_the_header_reset`

#### Scenario: a 429 with no reset hint waits five minutes

- **Given** an HTTP 429 with no `RateLimit` header and no `Retry-After`
- **When** the shared wait is computed
- **Then** the wait is 300 seconds
- **Test:** `tests/test_hf_auth.py::test_rate_limit_wait_defaults_to_five_minutes`

#### Scenario: the wait never exceeds ten minutes

- **Given** an HTTP 429 whose `RateLimit` header says `t=900`
- **When** the shared wait is computed
- **Then** the wait is 600 seconds
- **Test:** `tests/test_hf_auth.py::test_rate_limit_wait_caps_at_ten_minutes`

#### Scenario: the top-tier GET uses that wait, then succeeds

- **Given** a Hub GET that returns HTTP 429 with `RateLimit: "api";r=0;t=12`, then HTTP 200 with a JSON body
- **When** the top-tier GET is retried
- **Then** the sleep before the second attempt equals the shared wait for that 429
- **And** the returned value is that JSON body
- **Test:** `tests/test_llama_ai.py::test_hf_get_waits_out_a_429_using_the_shared_wait`

#### Scenario: a success resets the consecutive 429 count

- **Given** a Hub GET that returns 429, then 200, then 429, then 429, then 200
- **When** the top-tier GET is retried with a budget of two 429 retries
- **Then** the call returns the last JSON body
- **Test:** `tests/test_llama_ai.py::test_hf_get_resets_the_429_count_after_success`

#### Scenario: a third consecutive 429 fails

- **Given** a Hub GET that returns HTTP 429 three times
- **When** the top-tier GET is retried with a budget of two 429 retries
- **Then** the call fails
- **And** the third 429 was not followed by another attempt
- **Test:** `tests/test_llama_ai.py::test_hf_get_retries_transient_and_fails_permanent`

#### Scenario: a 404 is not retried

- **Given** a Hub GET that returns HTTP 404
- **When** the top-tier GET is made
- **Then** the call fails on that first attempt
- **Test:** `tests/test_llama_ai.py::test_hf_get_retries_transient_and_fails_permanent`

#### Scenario: the model listing uses the same wait

- **Given** a model-listing GET that returns HTTP 429 with `RateLimit: "api";r=0;t=12`, then a JSON list
- **When** the listing is fetched
- **Then** the sleep before the second attempt equals the shared wait for that 429
- **And** the returned value is that JSON list
- **Test:** `tests/test_trend_pick.py::test_hub_json_waits_out_a_429_using_the_shared_wait`

### Requirement: Every Hub download GET goes through one opener

A script that downloads from the Hub, or looks up a file size for a download, MUST open that URL with `hub_open` in `scripts/hf_auth.py`. `hub_open` MUST authorize the request, and on HTTP 429 it MUST wait `rate_limit_wait` and retry twice. A response that is not HTTP 429 MUST reset the consecutive-429 count. A caller MUST NOT call `urlopen` on a Hub URL itself.

The size lookup (`scripts/hf_download.py`), the ranged chunk download (`download_chunk`) and the preflight probe (`_probe_file_downloadable`) MUST use `hub_open`.

#### Scenario: the size lookup waits out a 429

- **Given** a tree listing that returns HTTP 429 with `RateLimit: "api";r=0;t=12`, then a JSON tree naming the file and its size
- **When** the downloader resolves the file size
- **Then** the sleep equals `rate_limit_wait` for that 429
- **And** the resolved size is the size in the tree
- **Test:** `tests/test_hf_download_retry.py::test_size_lookup_waits_out_a_429`

#### Scenario: the chunk download waits out a 429

- **Given** a ranged file GET that returns HTTP 429 with `RateLimit: "api";r=0;t=12`, then the file bytes
- **When** the chunk download runs
- **Then** the sleep equals `rate_limit_wait` for that 429
- **And** the written file is those bytes
- **Test:** `tests/test_hf_download_retry.py::test_chunk_download_waits_out_a_429`

#### Scenario: the preflight probe waits out a 429

- **Given** a ranged resolve GET that returns HTTP 429 with `RateLimit: "api";r=0;t=12`, then a body whose first four bytes are `GGUF`
- **When** the preflight probe runs
- **Then** the sleep equals `rate_limit_wait` for that 429
- **And** the probe returns `ok`
- **Test:** `tests/test_hf_download_retry.py::test_preflight_probe_waits_out_a_429`

#### Scenario: a third consecutive 429 fails the download GET

- **Given** a Hub GET that returns HTTP 429 three times
- **When** `hub_open` is called
- **Then** the call raises that 429
- **And** no fourth attempt is made
- **Test:** `tests/test_hf_download_retry.py::test_hub_open_fails_on_the_third_429`

