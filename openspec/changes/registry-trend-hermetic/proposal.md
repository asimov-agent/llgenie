---
name: registry-trend-hermetic
about: the hermetic unit gate detects, and no longer carries, a live fetch to a non-Hub host reached through a helper module
status: active
---

# The gate sees any live host, not just the Hub (issue #1067)

## Proposal

`tests/test_registry_sync_trend.py` made a live network fetch inside the hermetic `ci-unit` gate. Its
module-scoped `live_sync` fixture called `sync_registry.sync(sr.UPSTREAM, dest, sr.UPSTREAM_README)`,
and `sync_registry.UPSTREAM` resolves to
`https://raw.githubusercontent.com/andyholst/trending-local-llms/master/data/models.json`, fetched by
`urllib.request.urlopen` inside `sync_registry.fetch`. That file is selected by `make test-unit`
(`tests/fixtures/unit-suite.json` neither excludes nor deselects it), so the gate depended on GitHub
raw being reachable **on every run**, for tests that carried no marker and no exclusion.

The #1000 seam (`-m "not network"`) existed and would have excluded them the moment they were
marked. What was missing was the half that made them invisible: `tests/test_network_marker.py` judged
"real reach" by scanning **the test file's own text** for a **Hub** host (`_HUB_RE` is
`(huggingface\.co|hf\.co)`). This reach was neither — a different host, and inside a different
module — so the pin was green on a tree where a live fetch sat in the gate.

## Motivation

Measured at `main@36cfa8c1` (this change's base) over the hermetic selection, with the new scan:

```
selected files: 157
offenders: 3
  tests/test_registry_sync_trend.py::test_live_sync_adopts_a_higher_skilled_tps_for_models_that_fit_48gb
      (via fixture live_sync): live fetch to raw.githubusercontent.com via sync_registry.sync
  tests/test_registry_sync_trend.py::test_rank_follows_the_given_vram_ram_and_arch
      (via fixture live_sync): live fetch to raw.githubusercontent.com via sync_registry.sync
  tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it
      : live fetch to raw.githubusercontent.com via sync_registry.fetch
```

The same scan on the tree with this change applied reports `offenders: 0`.

The cost is already on the board: PR #932's `linux / unit` and `linux / install` jobs both died at
head `0a710920` with `urllib.error.HTTPError: HTTP Error 429: Too Many Requests [hf_auth] …
(HUB_RATE_LIMIT_BUDGET)` — a live call inside the gate, not that PR's diff.

## Change

- `tests/test_network_marker.py`: a second, wider pin. `module_network_reach()` resolves, per repo
  module, which functions can reach a **remote** host — transitively along that module's own call
  graph, with URLs resolved through module constants and f-strings — and `remote_reach_opens()` flags
  a call to one of them from a test, or from a pytest fixture an **unmarked** test actually requests,
  naming the host it saw (`raw.githubusercontent.com via sync_registry.sync`). A helper whose URL is
  assembled from an argument (`load_registry(src)`) counts only when the call site hands it something
  that resolves to a remote URL, so hermetic callers passing committed paths stay clean; a scope that
  replaces the transport (`def urlopen(...)`, `monkeypatch.setattr(…, "urlopen")`) makes no real call;
  and node ids the roster already de-selects are not part of the gate.
- `tests/test_registry_sync_trend.py`: the two live tests carry `@pytest.mark.network` (the
  #1000/#1002 seam moves them to `make test-unit-network` / `ci-hf-live.yml`), and **the same
  behaviour is asserted hermetically** against the committed store (`data/models.json` +
  `data/trending-README.md`) by two twins that call the identical helper bodies. No assertion is
  weakened and none is dropped.
- `tests/test_trend_pick.py`: the widened scan found a **second instance of the same class** — two
  `sr.fetch` calls to the live contract over `raw.githubusercontent.com` — so it carries the marker
  too, and its hermetic half (the committed store satisfies the committed contract) is its own test.
- `tests/test_check_model_links.py`: the routing census grows both files above, so unmarking either
  test reds the census instead of quietly putting a live fetch back into the gate.
- `pytest.ini`: the `network` marker is defined as "reaches a real network host", not "the Hub only".
- `agent-wiki/` note + `docs/changes.d/` fragment; `CHANGES.md` re-rendered with `make changes-index`.

## Acceptance

- [x] The files this change owns (`tests/test_network_marker.py`, `tests/test_registry_sync_trend.py`,
      `tests/test_check_model_links.py`, `tests/test_ci_hf_live_workflow.py`) are green under
      `docker run --network none` — 30 passed, 2 deselected — so the trend-registry suite and its pin
      perform **zero** network I/O, and the same ranking behaviour still runs hermetically against the
      committed store.
- [x] Measured and reported, NOT fixed here: the full gate under `--network none` is still not green —
      `tests/test_engine_supported_quants.py::test_pick_is_a_real_catalog_link` waits on the live Hub
      (`mp.matrix → gguf_repo → _hub_json → hub_open`) and two further tests fail in the first 6%,
      all through `scripts/hf_auth.hub_open`, which this scan does not follow across modules. That is
      a separate work item (#1059/#1020 class), disclosed on the issue rather than folded in here.
- [x] `tests/test_network_marker.py` has a negative control: an unmarked test reaching a **non-Hub**
      host **through a helper module** is named with host and helper; the same call under the marker,
      and a conditional helper handed a committed path, are not.
- [x] The gate's report names the host it saw.
- [x] The new rule names 3 violations against the old tree (marks stashed) and 0 against the fixed
      one, so it is proven to catch the bug rather than decorate the fix.
- [x] `make lint`, `make check-wiring`, `make check-docs`, `make check-workflows`,
      `make check-pr-hygiene`, `make openspec-tasks-check` and
      `make openspec-validate NAME=registry-trend-hermetic` exit 0.
