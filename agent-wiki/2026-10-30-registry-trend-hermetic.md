# 2026-10-30 — the hermetic gate sees any live host, not just the Hub (#1067)

**Issue:** [#1067](https://github.com/asimov-agent/llgenie/issues/1067) · **Branch:** `fix/1067-registry-trend-hermetic`
· **Base:** `main@36cfa8c1`

## What was wrong

`tests/test_registry_sync_trend.py` downloaded the live upstream registry on **every** `ci-unit` run.
Its module-scoped `live_sync` fixture called `sync_registry.sync(sr.UPSTREAM, dest, sr.UPSTREAM_README)`,
and `sync_registry.UPSTREAM` is
`https://raw.githubusercontent.com/andyholst/trending-local-llms/master/data/models.json`, opened by
`urllib.request.urlopen` inside `sync_registry.fetch` (`scripts/sync_registry.py:43-45`, `:257`). The
file is selected by the gate (`tests/fixtures/unit-suite.json` neither excludes nor deselects it), so
PR #932's `linux / unit` and `linux / install` died at `0a710920` with
`HTTP Error 429: Too Many Requests [hf_auth] (HUB_RATE_LIMIT_BUDGET)` — a live call inside the gate,
not that PR's diff.

## Why the existing pin could not see it

`tests/test_network_marker.py` (#1000) judged "real reach" by scanning **the test file's own text**
for a **Hub** host: `_HUB_RE = (huggingface\.co|hf\.co)`. This reach was neither — another host, and
inside another module — so the pin stayed green over a known defect. A guard that cannot be shown to
fail is decoration.

## What changed

- `tests/test_network_marker.py`: `module_network_reach()` builds, per repo module, the set of
  functions that can reach a **remote** host (transitively along that module's own call graph, URLs
  resolved through module constants and f-strings), and `remote_reach_opens()` flags a call to one of
  them from an unmarked test — or from a pytest fixture an unmarked test actually requests — naming
  the host (`raw.githubusercontent.com via sync_registry.sync`). Three carve-outs keep it honest:
  a helper whose URL is built from an argument counts only when the call site hands it a remote URL
  (`load_registry(src)` / `sync(local, …)` stay clean); a scope that stubs the transport
  (`def urlopen(...)`, `monkeypatch.setattr(…, "urlopen")`) makes no call; and node ids the roster
  already de-selects are not in the gate.
- `tests/test_network_marker.py` also fixes a latent crash in the #1000 scan: its URL-literal
  `match.group(3)` addressed a regex with two groups, so any primitive-call line that was not a
  string literal killed the pin with `IndexError` instead of reporting a finding.
- `tests/test_registry_sync_trend.py`: the two live tests carry `@pytest.mark.network`;
  `vendored_sync` + two twins assert the **identical** ranking behaviour on `data/models.json` +
  `data/trending-README.md`. Nothing was weakened or dropped.
- `tests/test_trend_pick.py`: the widened scan found a **second** instance — two live `sr.fetch`
  calls to the contract on `raw.githubusercontent.com` — marked, with its hermetic half (committed
  store satisfies the committed contract) kept as its own test.
- `tests/test_check_model_links.py`: the routing census grows both files, so unmarking either reds it.
- `pytest.ini`: the `network` marker means "reaches a real network host", not "the Hub only".

## Proof

- New scan against the **old** tree (the two marked files stashed): `1 failed`, naming **3** offenders,
  each with its host and helper.
- New scan against the fixed tree: `12 passed`, and green again under `docker run --network none`.
- The files this change owns, under `docker run --network none`: `30 passed, 2 deselected` — zero
  network I/O.
- `make test-unit`: `15042 passed, 16 deselected`.

## Left open (reported, not fixed here)

- **The full gate is still not hermetic.** Under `docker run --network none` the whole selection fails
  in the first 6% and stalls 5 minutes in
  `tests/test_engine_supported_quants.py::test_pick_is_a_real_catalog_link`
  (`mp.matrix → gguf_repo → _hub_json → hub_open`, `scripts/hf_auth.py:186`). Every one of those reaches
  goes through `hf_auth.hub_open`, whose `open_fn = opener or urllib.request.urlopen` the scan cannot
  follow across modules — so this class needs its own issue and lane, not a widening of this one.
- Live-data drift inside the two marked tests is #1064's business (they now run in the live pipeline,
  not the gate).
- The README-source seam of the same file is #1068, deliberately not touched here.
