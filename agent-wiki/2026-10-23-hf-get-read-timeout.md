# 2026-10-23 — a read-phase Hub timeout is retried, not fatal

Issue: [#549](https://github.com/asimov-agent/llgenie/issues/549)
PR: [#550](https://github.com/asimov-agent/llgenie/pull/550)
OpenSpec change: `hf-get-read-timeout`

## What was red

`main` at `ecdeb67` (run 39918511555, 2026-10-23T07:33Z) failed exactly one job, `macos / top-tier`:
`tests/test_top_tier_acceptance.py::test_family_dry_run_known_lowend_one_provider` — "dry run must exit 0"
— with `TimeoutError: The read operation timed out` raised through `ssl.py` in the subprocess's stderr.
The seven CI runs before it were green, and the push's own change was the auto-merge deferral recheck, so
this was a transient network stall, not a regression.

## Root cause

`scripts/llgenie_serve.py::_hf_get` retried `urllib.error.HTTPError` and `urllib.error.URLError`. A
**read-phase** timeout is the builtin `TimeoutError` (`socket.timeout` since 3.10), raised inside
`http.client`/`ssl` after the connection exists, and it is not a `URLError`:

```
$ python3 -c 'import urllib.error; print(issubclass(TimeoutError, urllib.error.URLError))'
False
```

So one slow read escaped the loop with no retry and no `[top-tier] HF API transient error … retrying`
line. `hf_auth.hub_open` already caught `(urllib.error.URLError, TimeoutError)` — the two Hub GET seams
disagreed on what a transport failure is.

## Fix

`_hf_get`'s transport arm now catches `(urllib.error.URLError, TimeoutError)`, so a stall rides the
existing `HF_GET_MAX_ATTEMPTS` budget and exponential backoff and, when spent, exits through the existing
`[ERROR] HF API still failing after N attempts` path.

## Verification

- `tests/test_llgenie_serve.py::test_hf_get_retries_a_read_phase_timeout` — a **real** local
  `ThreadingHTTPServer` that accepts and answers nothing (transport not monkeypatched): the first stall is
  retried and the retry's JSON returned; with a never-answering server and a budget of two, `SystemExit`
  after exactly two requests naming the attempt count, and no `TimeoutError` in the message.
- Falsified: with `scripts/llgenie_serve.py` stashed, the same test fails with `TimeoutError: timed out` —
  the CI symptom; restored, `5 passed` for the `-k "hf_get or read_phase_timeout"` selection.
- `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make check-pr-hygiene`, `make check-pr-authors`,
  `make openspec-validate NAME=hf-get-read-timeout`.

## Not covered

`ConnectionResetError` / `RemoteDisconnected` are still unretried by `_hf_get` (unmeasured here); #435 and
#339 own the other transient-failure seams.
