# 2026-11-13 — alias-preservation locked in the registry normalise seam (issue #2647)

## What was verified

- Issue #2647 claimed `scripts/sync_registry.py::normalise()` would silently drop the upstream
  optional row property `measurement_model_aliases` (upstream contract commit `447a9fa83`; live row
  `qwen3.6-35b-a3b -> ["qwen3-8-27b"]` by upstream `41539762d`). Re-measured at origin/main
  `298552b58`: the claim's mechanism is false. `normalise()` copies each row wholly
  (`row = dict(row)`) and the top level wholly (`out = dict(data)`), so the key survives.
- End-to-end fact now in the issue body: full CLI sync vs live upstream
  (`python3 scripts/sync_registry.py sync --dest <scratch>`, rc=0, `models=118`) — the synced store
  carries `qwen3.6-35b-a3b -> ['qwen3.8-27b']`; `scripts/registry_keys.py::compare(committed, synced)`
  reports 24 loss lines (store-age drift, issue #2503's scope), **0** naming the alias key.
- An earlier partial probe that called `sync()` without the measurements store produced a spurious
  `check_readme_matches` rejection ('vLLM' not in the row's known engines); the real CLI sync passes
  `measurements_src`/`posts_src` and is accepted. No upstream defect.
- Deliverable: two hermetic tests in `tests/test_registry_normalise.py` — a synthetic
  alias-carrying row keeps `measurement_model_aliases` verbatim through `normalise()` (alias-free
  rows gain nothing), and `registry_keys.compare()` names the alias loss in a hypothetical
  rebuild-drop while reporting none for the real pipeline. Focused container replay:
  `tests/test_registry_normalise.py` 9 passed, rc=0.

## Key decisions

- No production-code change: the pipeline already preserves the key; the lane locks the behaviour.
- The 24 compare drift lines are left to #2503 (upstream engagement refresh), named in `Not covered`.
- Issue body rewritten to the measured facts (OpenSpec change `sync-registry-alias-lock` is the
  referee); superseded probe claims replaced rather than commented around.

## Current status

- Branch `feat/sync-normalise-aliases-2647`; OpenSpec change `sync-registry-alias-lock`
  (proposal/spec/tasks written, validate pending at head); tests green focused; full battery +
  preflight + PR pending at final head.
