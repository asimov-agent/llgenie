# One Hub GET, one bounded transient budget

## Why

The repository has three implementations of "GET a Hub URL, wait out a 429, maybe retry a 5xx", and
their budgets have drifted apart (issue #339):

| path | budget before this change |
|---|---|
| `scripts/hf_auth.py::hub_open` — the seam every download uses | **no 5xx at all**: a 500/502/503/504 raised on the first answer |
| `scripts/model_engine_pick.py::_hub_json` | its own 3-try ladder, its own 429 counter, its own `urlopen` (IPv4-preferring) |
| `scripts/llgenie_serve.py::_hf_get` | 8 tries with backoff (the only one that survived a 5xx storm) |

Measured in #256's thread: one `make test-unit` run reported 22 × HTTP 500 + 11 × HTTP 504 from this
class, `linux / unit` green and `macos / unit` red on the same commit. On
`chore/engine-bump-mlx` (#372) the pick's own ladder exhausted on a 429, and
`model_engine_pick._tree` — which catches *any* `HTTPError` as "missing or gated repo" — cached an
empty file tree for it, so `plan_download` returned `None` and `test_download_mlx_repo_snapshot_for_real`
failed with `assert plan`. A transient Hub answer became "this repo has no files" for the rest of the
process.

## What Changes

- **`scripts/hf_auth.py::hub_open`** becomes that one seam: the transient set is 429, 500, 502, 503,
  504 and transport failures; a 429 waits the Hub's own window (`rate_limit_wait`) at most
  `RATE_LIMIT_WAITS` times, everything else retries on a stated doubling ladder
  (`HUB_BASE_PAUSE`, `HUB_MAX_ATTEMPTS`), and a definitive status still raises on the FIRST answer.
  The transport is pluggable (`opener`), so a caller with a quirk — the pick prefers IPv4 on macOS
  runners — keeps it while using this policy.
- **`scripts/model_engine_pick.py`**: `_hub_open` is now "IPv4 transport + the shared budget";
  `_hub_json` drops its own retry ladder (and its 3-try `attempts` parameter); `_tree` no longer
  treats a transient status as a definitive one — a throttle or 5xx returns "unknown" **without
  caching an empty tree**, so the next call asks again instead of serving the blip as a fact.
- **`tests/test_hub_transient_budget.py`** (new, wired into `test-unit`): a REAL loopback Hub
  (`http.server` on 127.0.0.1) whose scripted answers prove the budget by its own request count —
  503 then 206, an eternal 503 (bounded, loud), a definitive 404 (one request), an eternal 429
  (two window waits then stop) — plus the pick stack on top of it: a 503 is retried into a real tree,
  and an eternal 429 is never cached as an empty repo.

## Impact

- A Hub 5xx storm or an exhausted rate-limit window no longer reddens a lane or silently empties a
  repository: it is waited out, and when it is genuinely over, it fails loudly with the status.
- `linux / unit` and `macos / unit` stop disagreeing about the same commit because one of them hit a
  different Hub window.
- Not in this change: `scripts/llgenie_serve.py::_hf_get` still carries its own (equivalent) ladder —
  deduping that third copy is what remains of issue #339, and this change does not close it.
