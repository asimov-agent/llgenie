# 2026-11-20 — Health model lands in the shared stage HOME (issue #356, PR pending)

## What was verified against the spec

- `make download-test-model` now runs the downloader with `HOME=$(CI_HOME)` in a
  uid-mapped container with the checkout mounted at its own path
  (`MODEL_CACHE_RUN`): the 0.43 GB health model landed at
  `.ci-home/models/Qwen/8GB/qwen2.5-0.5b-instruct-q4_0.gguf` (428,730,208 B,
  owner `asimov`) and survived the `--rm` container. Second run printed
  `already present` with rc=0 — no network.
- `CI_HOME_CLEAN` (Linux variant, invoked verbatim via `make --eval`) removed
  `.ci-home/bin`, `.ci-home/.cache` and a seeded scratch file but kept the whole
  `models` subtree — the health stage's own download step now short-circuits
  against it (`env HOME=.ci-home python3 scripts/download_test_model.py` →
  `already present`, rc=0), so `make loop` fetches the model once.
- Darwin branch carries the same shape natively (`env HOME=$(CI_HOME)` run,
  models-keeping `find`-clean).
- Seams pinned by `tests/test_health_model_cache.py` (7 tests); targeted battery
  68/68 green incl. the pre-existing macos/split pins; openspec-validate rc=0.

## Key decisions

- The cache lives in the SAME HOME the engine stages already read (`.ci-home`),
  not a new location — one shared stage HOME instead of two caches.
- `CI_HOME_CLEAN` keeps its name, its root-run shape (#2563) and every call
  site; only its scope changed (everything except `models`).
- Host-side serving proof ("hi") stays with CI's `cpu-health` job — starting
  inference engines on the host needs explicit human permission.

## Current status

OpenSpec change `download-test-model-cache` validated; all implementation tasks
proven locally; unit battery + lane-preflight queued; PR to `main` pending push.
