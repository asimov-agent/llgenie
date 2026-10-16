# hub-probe-retry

## ADDED Requirements

### Requirement: one live-Hub probe serves every live-Hub suite

The test suite MUST verify a real Hugging Face link through ONE shared probe (`tests/hub_probe.py`), not a
per-file copy. The probe MUST issue the ranged `GET` (`Range: bytes=0-0`, `User-Agent: llgenie-test`),
report existence from `200`/`206`, and return the **status or transport reason** it observed, so a red test
names an upstream `5xx`/`429`/timeout distinctly from a genuinely absent file.

WHEN a live-Hub link is probed
THEN the answer is a `Probe(exists, detail, attempts)` whose `detail` carries the HTTP status (e.g.
`HTTP 206`, `HTTP 404`) or the transport error, and no second implementation of the ranged GET exists in
`tests/`.

#### Scenario: a green link reports the status it saw

- **Given** a Hub URL that answers `206` to a ranged GET
- **When** the shared probe verifies it
- **Then** `exists` is true, `detail` is `HTTP 206`, and exactly one request was made
- **Test:** `tests/test_hub_probe.py::test_a_present_file_is_one_request_and_reports_the_status`

#### Scenario: an absent file is definitive and is not retried

- **Given** a Hub URL that answers `404`
- **When** the shared probe verifies it
- **Then** `exists` is false, `detail` is `HTTP 404`, and exactly one request was made
- **Test:** `tests/test_hub_probe.py::test_a_missing_file_is_one_request_and_says_404`

#### Scenario: a definitive status that is neither 200 nor 404 is also one request

- **Given** a Hub URL that answers `204`
- **When** the shared probe verifies it
- **Then** `exists` is false, `detail` is `HTTP 204`, and `attempts` is 1 — the retry budget it never spent
  is not claimed in the message
- **Test:** `tests/test_hub_probe.py::test_a_definitive_non_404_status_is_not_retried_and_reports_its_own_attempt_count`

#### Scenario: both live-Hub suites use the shared probe

- **Given** the committed `tests/test_pick_full_registry.py` and `tests/test_trending_quant_catalog.py`
- **When** each needs to verify a link
- **Then** it calls `hub_probe.probe` and prints its `detail` in the failure message, and neither file
  defines its own `_url_exists`
- **Test:** `tests/test_hub_probe.py::test_every_live_link_probe_in_the_suite_is_the_shared_one`

### Requirement: a bounded retry budget covers the transient upstream set

The probe MUST retry `429`, `500`, `502`, `503`, `504`, `URLError`, `TimeoutError` and `OSError` on a
bounded ladder (1 s, 2 s, 4 s, 8 s — at most 5 attempts) and MUST stop after that budget with the cause in
`detail`. It MUST NOT retry a definitive answer.

WHEN the Hub answers a transient status, or the connection fails transiently
THEN the probe retries within its budget and returns the first success.

#### Scenario: a transient 503 is retried and the link verifies

- **Given** a Hub URL that answers `503` once and then `206`
- **When** the shared probe verifies it
- **Then** `exists` is true, `detail` is `HTTP 206`, and exactly two requests were made
- **Test:** `tests/test_hub_probe.py::test_a_transient_5xx_is_retried_before_the_link_is_called_missing`

#### Scenario: a sustained failure stops at the budget, with the ladder it waited

- **Given** a Hub URL that answers `503` on every attempt
- **When** the shared probe verifies it
- **Then** `exists` is false, `detail` names `HTTP 503` and the 5 exhausted attempts, and the recorded waits
  are exactly `[1, 2, 4, 8]`
- **Test:** `tests/test_hub_probe.py::test_a_sustained_5xx_stops_at_the_budget_and_reports_the_ladder`

#### Scenario: a transport failure is not an absent file

- **Given** a port where nothing listens
- **When** the shared probe verifies a URL on it
- **Then** `exists` is false and `detail` names the transport error, never `HTTP 404`
- **Test:** `tests/test_hub_probe.py::test_a_transport_failure_is_reported_as_the_transport_error`

### Requirement: a sustained outage cannot multiply the retry budget

Once `OUTAGE_LIMIT` probes in one process have exhausted the retry budget on a transient outcome, every
later probe MUST take a single attempt and say the Hub is in a degraded window. This is a time bound, never
a skip: the unverified links MUST still fail their assertions.

WHEN the Hub is in a sustained outage and many links are probed
THEN the added waiting stays bounded and each unverified link still fails loudly.

#### Scenario: the breaker caps the waiting after the outage limit

- **Given** a Hub that answers `503` forever and `OUTAGE_LIMIT` probes that have already exhausted the budget
- **When** the next link is probed
- **Then** that probe makes exactly one request and its `detail` says the Hub is in a degraded window
- **Test:** `tests/test_hub_probe.py::test_the_outage_breaker_caps_the_attempts_after_the_limit`
