# hf-get-read-timeout

## ADDED Requirements

### Requirement: a read-phase Hub timeout is retried, not fatal

`scripts/llgenie_serve.py::_hf_get` MUST treat a **read-phase socket timeout** as a transient transport
failure: it is the builtin `TimeoutError`, raised from `http.client`/`ssl` after the connection is
established, and it is NOT a `urllib.error.URLError` subclass. The retry loop MUST therefore name both
classes, retry on the existing `HF_GET_MAX_ATTEMPTS` budget with the existing exponential backoff, print
the existing transient-error line, and — with the budget spent — exit through the existing
`[ERROR] HF API still failing after N attempts` path. A `TimeoutError` MUST NOT escape as a traceback.

WHEN a Hub GET's connection is accepted and the read then times out
THEN `_hf_get` retries it, and a later answer is returned as if the stall had not happened.

#### Scenario: a stalled read is retried and the retry's answer returned

- **Given** a real local HTTP server that accepts the connection and answers nothing on the first request,
  and answers JSON on the next
- **When** `_hf_get` is called with a timeout shorter than the stall
- **Then** it returns the retry's payload and the server saw two requests
- **And** no `TimeoutError` reaches the caller
- **Test:** `tests/test_llgenie_serve.py::test_hf_get_retries_a_read_phase_timeout`

#### Scenario: an exhausted budget fails with the retry loop's own message

- **Given** a real local HTTP server that accepts every connection and never answers
- **When** `_hf_get` runs with a budget of two attempts
- **Then** it raises `SystemExit` after exactly two requests, whose message is
  `[ERROR] HF API still failing after 2 attempts …`
- **And** the raised message names no `TimeoutError`
- **Test:** `tests/test_llgenie_serve.py::test_hf_get_retries_a_read_phase_timeout`

### Requirement: the two Hub GET seams agree on what a transport failure is

`_hf_get` and `scripts/hf_auth.py::hub_open` MUST both retry the same transport-failure classes
(`urllib.error.URLError` and `TimeoutError`), so one Hub path cannot be resilient where the other is fatal
for the identical network condition.

WHEN the transport arms of the two seams are compared
THEN both name `urllib.error.URLError` and `TimeoutError`

#### Scenario: a stalled read fails identically in neither path

- **Given** the two Hub GET seams, `hf_auth.hub_open` and `llgenie_serve._hf_get`
- **When** each one meets a connection that is accepted and then never answers
- **Then** both treat it as transient (retry on their own budget) rather than raising the raw
  `TimeoutError` at the caller
- **Test:** `tests/test_llgenie_serve.py::test_hf_get_retries_a_read_phase_timeout` (the `_hf_get` half;
  the `hub_open` half is `tests/test_hub_transient_budget.py`), plus the falsification recorded in
  `agent-wiki/2026-10-23-hf-get-read-timeout.md` — with the source un-patched the first scenario fails
  with `TimeoutError: timed out`.
