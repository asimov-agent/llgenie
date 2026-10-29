# bound-unit-network-waits — 2026-10-29

## What changed

- `scripts/model_engine_pick.py`
  - `DOWNLOAD_TIMEOUT` — the outer ceiling on ONE `scripts/hf_download.py` child, default 3600 s,
    overridable with `LLGENIE_DOWNLOAD_TIMEOUT`. The 3600 is derived from the child's own bound, not
    picked: `hf_download.py` runs `MAX_RETRY = 20` attempts on a 90 s stall-watch and a 5 s pause
    (≈1900 s of retry ladder), so ~2x that still lets a healthy download that retries finish.
  - `download()` passes `timeout=DOWNLOAD_TIMEOUT` to `subprocess.run` and catches
    `subprocess.TimeoutExpired`, re-raising `SystemExit` that names the repo/file, the seconds exceeded
    and the full command. Before this, the call had no `timeout=` at all.
- `scripts/hf_auth.py`
  - `RATE_LIMIT_TOTAL_BUDGET` (default 60 s, `HUB_RATE_LIMIT_BUDGET` overrides) — the total ONE
    `hub_open` lookup may sleep on 429s, **in addition to** the existing `RATE_LIMIT_WAITS` count.
  - `hub_open` keeps per-lookup `waits`/`slept`, and raises when the count ceiling is passed OR when
    the next Hub window would not fit the remaining total. A 429 whose window does not fit raises at
    once: the Hub's `t` is what is left of a fixed 5-minute window, so sleeping less spends the next
    window on another 429.
  - `_rate_limited_error()` re-raises the **same** 429 (Hub status and headers unchanged, so callers
    reading `e.code`/`e.headers` are unaffected) with a message stating the attempts, the 429 waits,
    the seconds slept and the budget.

## Why

`linux / unit` is 1:45:25 at its last green head (`14581 passed` in 1:31:47 of it) and nothing in it
was hung — but one hop inside it had no ceiling at all, and the faulthandler dumps named it:
`scripts/model_engine_pick.py:1465 in download` (`tests/test_trend_pick.py::test_download_mlx_repo_snapshot_for_real`).
Beneath that call, `hub_open` could spend TWO 600 s waits per lookup (20 minutes) and `unit` declares
no `timeout-minutes`, so GitHub's 6-hour default was the only limit. `pytest.ini`'s
`faulthandler_timeout = 300` prints a traceback and never kills.

## How it was proven

- Falsification first, against `HEAD`'s source with the new tests in place: the four bound tests fail
  — `slept == []` no longer holds (it slept the 600 s window) and
  `'timeout' in {'env': …}` is `False` — then restored, the same four pass.
- `llgenie/test:latest python -m pytest tests/test_hf_auth.py tests/test_model_engine_pick.py
  tests/test_hub_transient_budget.py tests/test_hf_download_retry.py -q` → **38 passed**, i.e. the
  existing 429 policy (`slept == [1, 1]`, three requests, no fourth attempt) is untouched by the new
  total.
- The loud-failure half is real, not recorded: an `hf` CLI stub that sleeps past a 2 s ceiling makes
  `download()` exit naming `hf_download.py`, `model.gguf` and `exceeded 2s`.

## Decisions

- **A total, not a smaller per-wait cap.** Lowering `RATE_LIMIT_WAIT_CAP` would change what
  `rate_limit_wait` means for `llgenie_serve.py` and the tests that assert it; the total bounds the
  aggregate (the thing that held the runner) and leaves the shared policy function alone.
- **The same exception type, with a message.** Callers (`hf_download`, `download_chunk`,
  `_probe_file_downloadable`, `_hub_json`) branch on `e.code`, so a new exception class would be a
  behavioural change beyond this bound; `msg` is where the diagnosis belongs.
- **3600 s for a download** because a real GGUF is multi-GB on an unknown link; the bound is a
  hang-detector, and it is overridable where it is a budget (a deliberately slow mirror).

## Not covered

- Job ceilings (`timeout-minutes`) — #882, and not before, because its `60` on `unit` is below the
  observed green maximum (1:45:46).
- Killing the child's grandchildren on timeout (process-group kill): the runner's orphan cleanup
  handles it today; a separate change with its own evidence.
- The suite's 14.5 k live-Hub calls behind a PR gate — its own decision.

Refs: #872 (the bound), #797 (a timeout must never look like empty output), #339 / #163 (the shared
429 policy this bounds), #549 (the read-phase timeout in the sibling seam).
