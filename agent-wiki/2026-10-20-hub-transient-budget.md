# One Hub GET, one bounded transient budget (issue #339, part of it)

**Issue:** [#339](https://github.com/asimov-agent/llgenie/issues/339) (this change is part of it; it
does **not** close the issue) · **Change:** `openspec/changes/hub-transient-budget`

## What was wrong

Three implementations of "GET a Hub URL, wait out a 429, maybe retry a 5xx", with budgets that had
drifted apart:

- `hf_auth.hub_open` — the seam every download uses — had **no 5xx handling at all**: a 500/502/503/504
  raised on the first answer. Measured in #256's thread: one `make test-unit` run reported
  22 × HTTP 500 + 11 × HTTP 504, `linux / unit` green and `macos / unit` red on the same commit.
- `model_engine_pick._hub_json` carried its own 3-try ladder and its own `urlopen`, so on
  `chore/engine-bump-mlx` (#372) an exhausted 429 raised — and `_tree`, which caught *any* `HTTPError`
  as "missing or gated repo", cached an empty file tree for it. `plan_download` then returned `None`
  and the lane failed with `assert plan`. One transient answer became "this repo has no files" for the
  rest of the process.

## What changed

- **`hf_auth.hub_open` is that one seam**: the transient set is 429, 500, 502, 503, 504 and transport
  failures; a 429 waits the Hub's own window (`rate_limit_wait`) at most `RATE_LIMIT_WAITS` times,
  everything else retries on a stated doubling ladder (`HUB_BASE_PAUSE` × 2ⁿ, `HUB_MAX_ATTEMPTS`), and
  a definitive status still raises on the FIRST answer. The transport is pluggable (`opener`).
- **`model_engine_pick`**: `_hub_open` = the IPv4 transport passed as that `opener` + the shared
  budget; `_hub_json` dropped its own ladder; `_tree` returns "unknown" for a transient status
  **without caching** the empty tree, so the next call asks the Hub again.

## Verified

Real loopback Hub (`http.server` on 127.0.0.1), the budget proved by the server's own request count
(`tests/test_hub_transient_budget.py`, 6 tests):

```
503,503,200 → the answer, after exactly 3 requests
503 forever → raises 503, after exactly 3 requests
404         → raises, after exactly 1 request
429 forever (t=1) → waits the window twice, raises on the 3rd
pick: 503,200 → the repo's file, after 2 requests
pick: 429 forever → [] twice, the Hub asked again, no cached empty tree
```

Plus the four neighbouring suites unchanged by the refactor: `test_hf_auth.py`,
`test_hf_download_retry.py` (the 429 budget and the size-lookup waits still hold),
`test_model_engine_pick.py`, `test_llgenie_serve.py` — **268 passed**.

## Not covered

`scripts/llgenie_serve.py::_hf_get` still carries its own (equivalent) ladder; deduping that third copy
is what remains of #339.
