# hf-get-read-timeout — proposal

Issue: [#549](https://github.com/asimov-agent/llgenie/issues/549)

## Why

`main` at `ecdeb67` is red on one job, `macos / top-tier`, and the push's own change (the auto-merge
deferral recheck) has nothing to do with it. The real CLI's family dry run exited 1 with a traceback:

```
FAILED tests/test_top_tier_acceptance.py::test_family_dry_run_known_lowend_one_provider
  AssertionError: dry run must exit 0; stderr:
    File ".../http/client.py", line 286, in _read_status
    File ".../socket.py", line 706, in readinto
    File ".../ssl.py", line 1166, in read
    TimeoutError: The read operation timed out
  assert 1 == 0
```

`scripts/llgenie_serve.py::_hf_get` — the top-tier discovery GET — retries `HTTPError` and `URLError`. A
**read-phase** socket timeout is neither: `socket.timeout` is the builtin `TimeoutError` since Python 3.10,
raised from inside `http.client`/`ssl` after the connection is established, and
`issubclass(TimeoutError, urllib.error.URLError)` is `False`. So one slow read left the retry loop
uncaught, no `[top-tier] HF API transient error … retrying` line was printed, and the CLI died with an
`ssl.py` traceback.

The sibling seam already does the right thing: `scripts/hf_auth.py::hub_open` catches
`(urllib.error.URLError, TimeoutError)`. The two seams disagreed on what a transport failure is, and the
top-tier path lost.

## What Changes

- **`scripts/llgenie_serve.py::_hf_get`**: the transport arm catches `(urllib.error.URLError, TimeoutError)`,
  so a read-phase timeout is retried on the existing `HF_GET_MAX_ATTEMPTS` budget with the existing
  exponential backoff, prints the existing `[top-tier] HF API transient error … retrying` line, and — when
  the budget is spent — exits through the existing `[ERROR] HF API still failing after N attempts` path
  instead of a traceback. The docstring states why the two exception classes are both named.
- **`tests/test_llgenie_serve.py`**: `test_hf_get_retries_a_read_phase_timeout` — a REAL local HTTP server
  that accepts the connection and answers nothing (no monkeypatched transport), proving a stall is retried
  and its retry's payload returned, that an exhausted budget raises `SystemExit` naming the attempt count,
  and that `TimeoutError` never escapes.
- **`README.md`**: the Hub-transport paragraph says a read-phase timeout is a `TimeoutError`, not a
  `URLError`, and that both Hub GET seams retry it (issue #549).
- **`agent-wiki/2026-10-23-hf-get-read-timeout.md`**: the dated work record.

## Not covered

- The other transient transport classes (`ConnectionResetError`, `http.client.RemoteDisconnected`): only
  the read timeout is measured here. Retrying them is its own change with its own evidence.
- #435 (the README link probe's 15 un-retried Hub requests) and #339 (`hub_open`'s 5xx handling): same
  family of transient-failure gaps, different seams, their own issues.
- Re-running `main`'s red run: a re-run of 39918511555 exercises the same live network again; the fix is
  proven by the hermetic test (falsified against the unfixed source) and by the next `top-tier` job.

Refs: #161 (retry a timed-out read with a new request), #163 (the 429 window), #61 (the fan-out's retry
budget), #546 (the commit whose push run exposed this).
