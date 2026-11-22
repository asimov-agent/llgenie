## ADDED Requirements

### Requirement: a DEAD classification is committed only after the bounded retry budget
The quant-catalog link probe SHALL commit a link to `dead` only after a BOUNDED retry budget: when an attempt answers 404, 410, any 5xx, or a transport error, `_probe_status` SHALL retry the same URL up to `PROBE_ATTEMPTS` total attempts with a short backoff between them and SHALL classify on the FINAL answer only — a link that answers 200/206 on any later attempt is `ok`, not dead. A 200/206 and a 401/403 SHALL return on the FIRST attempt (a gated answer is a stable access decision, not a blip, and a healthy link pays no retry cost). The retry SHALL live only in `_probe_status`, the single live-probe classification shared by the sync carry-over drop path and the `compare` check failure path; callers that inject a `probe=` seam (hermetic replay, unit tests) bypass it and never retry or sleep. A bounded retry budget SHALL NOT bless an unverifiable link: a link whose attempts all fail is `dead` exactly as today, and the sync/check lines keep naming the probe class that fired.

#### Scenario: a flaky 404 that answers on retry is not dead
- **WHEN** a probe's first attempts answer 404 (or a 5xx, or a transport error) and a later attempt within the budget answers 200 or 206
- **THEN** `_probe_status` returns `ok` and the plan is kept by the carry-over and check paths

#### Scenario: a link dead across the full budget is still dead, loudly
- **WHEN** every attempt within `PROBE_ATTEMPTS` answers 404/410
- **THEN** `_probe_status` returns `dead` and the drop/check lines report the link exactly as today ("answers 404/410")

#### Scenario: a gated answer is classified without retry
- **WHEN** an attempt answers 401 or 403
- **THEN** `_probe_status` returns `gated` after exactly ONE request — gated is not retried

#### Scenario: the retry is inside the live classifier only
- **WHEN** `carry_over` or `compare` runs with an injected `probe=` seam (hermetic replay, unit tests)
- **THEN** no retry loop or backoff sleep runs in the caller, and the injected answers classify exactly as passed

- **Test:** `tests/test_quant_catalog_compare.py` loopback scenarios for 404→200, 404×budget, 401-without-retry
