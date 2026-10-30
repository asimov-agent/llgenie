# bound-unit-network-waits — proposal

Issue: [#872](https://github.com/asimov-agent/llgenie/issues/872)

## Why

`linux / unit` was measured at **1:45:25** on its last green head (job `123147377978`, step 5
`make ci-unit`, of which `make test-unit` alone is 1:31:47 / `14581 passed`), and the maximum GREEN
over the last 30 completed `linux / unit` jobs is **1:45:46**. None of that is a stall: the time is
spread over ~19 blocks of ~72 tests whose Hub calls were slow. But *one* hop inside that suite is
genuinely unbounded, and it is the one the faulthandler dumps name:

```
scripts/model_engine_pick.py:1465  in download   ← tests/test_trend_pick.py:816
                                                     test_download_mlx_repo_snapshot_for_real
```

`subprocess.run([… hf_download.py …], env=env)` carried **no `timeout=`**, one child per planned
file. Beneath it everything was bounded but generous: `scripts/hf_auth.py::hub_open` slept the Hub's
429 window (`rate_limit_wait`, `RATE_LIMIT_WAIT_CAP = 600`) and `RATE_LIMIT_WAITS = 2` allowed **two**
of those per lookup — so a single throttled Hub read could hold for **20 minutes**. Nothing bounded
the aggregate: `pytest.ini`'s `faulthandler_timeout = 300` prints a traceback and never kills, and the
`unit` job declares no `timeout-minutes`, so GitHub's 6-hour default is the outer limit. A red that a
re-run cannot explain is cheaper to prevent than to reconcile, so the hop gets a ceiling and the
generous waits get a total.

## What Changes

- **`scripts/model_engine_pick.py::download`** passes an explicit `timeout=` to the `hf_download.py`
  child (`DOWNLOAD_TIMEOUT`, default 3600 s, `LLGENIE_DOWNLOAD_TIMEOUT` overrides it). On
  `subprocess.TimeoutExpired` it raises `SystemExit` naming the repo/file, the seconds it exceeded and
  the **full command** — a timeout is a loud failure, never an empty success (#797's class). The
  default is ~2x the child's own retry ladder (`hf_download.py`: `MAX_RETRY = 20` on a 90 s
  stall-watch and a 5 s pause ≈ 1900 s), so a healthy download that retries still finishes.
- **`scripts/hf_auth.py::hub_open`** bounds its 429 sleeps by a **total**, not only by a count:
  `RATE_LIMIT_TOTAL_BUDGET` (default 300 s — the Hub's real 5-minute window, `HUB_RATE_LIMIT_BUDGET` overrides it). A 429 whose Hub
  window does not fit what is left of that budget raises immediately instead of sleeping — sleeping
  less than the Hub's stated `t` only spends the next window on another 429. The count rule
  (`RATE_LIMIT_WAITS`) still applies; the two are independent ceilings. The raised 429 keeps the
  Hub's status and headers and gains a message stating the **attempts** spent, the waits spent and
  the budget it ran out of, so a rate-limited probe fails fast and says why.
- **`tests/test_hf_auth.py`** — three tests drive the real `hub_open`: a 600 s window fails before
  sleeping anything; the ceiling is a total (40 s of a 60 s budget, never 80); and the failure names
  the attempts and the budget.
- **`tests/test_model_engine_pick.py`** — two tests: the `timeout=` the child is given is the module's
  stated ceiling, and a REAL `hf` CLI that never returns is killed at the ceiling with a message
  naming `hf_download.py` and the file.

## Impact

- `scripts/hf_auth.py`, `scripts/model_engine_pick.py`
- `tests/test_hf_auth.py`, `tests/test_model_engine_pick.py`
- `agent-wiki/2026-10-29-bound-unit-network-waits.md`, `CHANGES.md`

## Not covered

- **Job ceilings** — `timeout-minutes` on `.github/workflows/*` is [#882](https://github.com/asimov-agent/llgenie/issues/882)'
  work, and its 60 on `unit` would red a run that passes at 1:45:46. This change bounds the hop the
  ceiling is meant to catch; the number can be lowered only after that.
- **The suite's size and its live-Hub dependence** (14.5 k Hub calls behind a PR gate; the
  Hub-probing checks `check-quant-catalog` / `check-trend-list-matrix` / `check-registry` are 10:32 of
  the same step) — a separate decision, not a refactor smuggled into a bound.
- **Killing the child's own children** — `subprocess.run(timeout=…)` kills `hf_download.py`; a
  grandchild `hf` process it had already spawned is left to the runner's orphan cleanup. Making the
  child a process group and killing the group is its own change with its own evidence.
- **A 429 that no longer waits its window at all** — the total budget is deliberately smaller than one
  Hub window, so a throttled *probe* now fails instead of surviving; a caller that must survive a
  window sets `HUB_RATE_LIMIT_BUDGET` and (with #882) a job ceiling sized to it.
