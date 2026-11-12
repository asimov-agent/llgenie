# Proposal: engine-selection-canonical

## Why

Issue #2561, measured on `main` = `aa700cf27`. The registry-liveness self-remediation wave dispatched 28 scoped `engine-build` push=true runs; nine completed `completed success` having built and published nothing — runs 43149732453, 43149735782, 43149739069, 43149741957, 43149744886, 43149748002, 43149751256, 43149753954, 43149757005, each with a build job named `engine-build-none-none` whose every step is skipped by `if: matrix.engine != 'none'`.

The ids are mangled upstream of the dispatch: the step derives engine ids by parsing GHCR package URLs (`grep 'NOT PUBLISHED' … | grep -oE '…ghcr\.io/…' | cut -d: -f1`), but package names legally replace dots with dashes (`scripts/engine_image.py:1246`, `params['id'].replace('.', '-')`). `llama.cpp` reaches the workflow as `engine=llama-cpp`. `scripts/engine_image.py matrix` then matches no params id and **fabricates** the placeholder row `{"engine": "none", …}` (`matrix()` 1279-1284) exiting 0 — so `make engine-build-matrix ENGINE=<typo>` and `make build-engines ENGINE=<typo>` are also silent green no-ops today. Nine cells of the three dotted engines stayed unpublished while the sweep reported success.

## What Changes

1. **`scripts/check_engine_pins_published.py`**: the ALL=1 sweep gains one machine-readable contract line per unpublished cell: `[select] <engine-id> <variant> <tag>` — the engine id from the committed params file (dots intact). The registry is a namespace where dots are illegal; the params id is the canonical name.
2. **`.github/workflows/registry-liveness.yml`**: the dispatch step builds its `gh workflow run` inputs ONLY from `[select]` lines — no engine id is reconstructed from a package URL.
3. **`scripts/engine_image.py`**: `matrix()` with an **explicit** `--engine` and/or `--arch` that resolves to zero committed cells exits non-zero naming the unresolved selection (`no committed engine id 'llama-cpp'`; `'llama.cpp' has no committed variant 'metal'`). The placeholder `engine: "none"` row remains ONLY for unscoped selections (`--changed` sweeps with nothing moved, whole-fleet sweeps) — the documented intentional no-op GitHub needs to keep a matrix legal.
4. **Tests** pin all three behaviours, including the replay of this incident (`--engine llama-cpp`, the package spelling, must hard-fail with a named error) and `[select]` lines carrying dotted ids.

## Impact

- Affected specs: engine-image selection (new requirement set `engine-selection-canonical`).
- Affected code: `scripts/engine_image.py`, `scripts/check_engine_pins_published.py`, `.github/workflows/registry-liveness.yml`, `tests/test_engine_image_matrix.py`, `tests/test_check_engine_pins_published.py`.
- Fleet remediation for the `aa700cf27` gap is already running: nine scoped push=true dispatches with canonical dotted ids were fired out-of-band; their drain to full publication is tracked by #2529 (this change's `Not covered`).
