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
  - `RATE_LIMIT_TOTAL_BUDGET` (default 300 s — the Hub's real 5-minute window, `HUB_RATE_LIMIT_BUDGET` overrides) — the total ONE
    `hub_open` lookup may sleep on 429s, **in addition to** the existing `RATE_LIMIT_WAITS` count.
  - `hub_open` keeps per-lookup `waits`/`slept`, and raises when the count ceiling is passed OR when
    the next Hub window would not fit the remaining total. A 429 whose window does not fit raises at
    once: the Hub's `t` is what is left of a fixed 5-minute window, so sleeping less spends the next
    window on another 429.
  - `_rate_limited_error()` re-raises the **same** 429 (Hub status and headers unchanged, so callers
    reading `e.code`/`e.headers` are unaffected) with a message stating the attempts, the 429 waits,
    the seconds slept and the budget.
- **The same bound, applied to the gate's own traffic** (the `linux / unit` red at `1bf1eea7`, job
  `124213872957`: `42 failed, 14987 passed`): the suite behind that gate still resolved live Hub
  answers, so the first 429 window it met starved 36 `tests/test_pick_full_registry.py` cases
  (`assert []`), red `tests/test_trending_quant_catalog.py`'s two `offer()` rules and
  `tests/test_trend_pick.py::test_hub_json_caches_and_survives_a_missing_repo`, and raised inside
  `tests/test_pick_matrix.py`'s two matrix cases. Now:
  - `tests/test_pick_matrix.py` answers `gguf_repo`'s **search** from the fixture
    (`monkeypatch.setattr(mp, "_hub_json", lambda url: [])`) in its autouse fixture, and its
    `--matrix` CLI case resolves the plan from the committed quant table
    (`LLGENIE_QUANT_CATALOG`) instead of the live tree — the module makes no Hub call at all.
  - `tests/test_pick_full_registry.py` (the SYSTEM matrix: real trees, real ranged HTTP 200 probes)
    carries a **module-level** `pytestmark = pytest.mark.network`, so all 40+ cases move to the
    `-m network` pipeline (#1002) in one line.
  - `test_trend_pick.py::test_hub_json_caches_and_survives_a_missing_repo`,
    `test_trending_quant_catalog.py::test_bounded_sample_of_real_links_exist_http_200` and its two
    `offer()` rules carry `@pytest.mark.network`; the data-path census
    (`tests/test_check_model_links.py::EXPECTED_NETWORK_TESTS`) records the `test_trend_pick` one.
  - `tests/test_network_marker.py` pins the module-level route (every case collected by
    `-m network`, none by `-m "not network"`), and its `mp.download` reach carve-out now recognises
    a **stubbed download child** — the regime #872's own bound tests use (one stubs
    `mp.subprocess.run` and records argv, the other points `HF_BIN` at a `sleep` script), so the pin
    stops calling hermetic #872 tests real reaches.

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
- The suite's remaining live-Hub calls behind a PR gate — its own decision. Measured while proving this
  round (`netlog` sitecustomize, `linux / unit`'s four routed modules excluded): `tests/test_trend_pick.py`'s
  `offer()`-driven list/CLI cases still resolve the Hub for models the committed table does not cover, so
  a 429 window can still red them; they are green on `main@564e938` and were not in this run's 42, so they
  are left for their own change rather than folded in here.

Refs: #872 (the bound), #797 (a timeout must never look like empty output), #339 / #163 (the shared
429 policy this bounds), #549 (the read-phase timeout in the sibling seam).
