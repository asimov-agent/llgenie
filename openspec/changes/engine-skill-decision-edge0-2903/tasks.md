# Tasks

- [x] Re-confirm the vendored registry carries the upstream `edge0` engine record and the `edge0-145b` model record after rebasing onto #2906's 120-model re-vendor (jq presence check on the rebased branch; no splice — the store stays single-sourced)
- [x] Replace the thin carried `edge0` decision reason in `data/unsupported-engines.json` with the upstream-read reason (decided 2026-11-18, issue 2903, reason from upstream README/releases/EDGE0.md; `backend`/`upstream` fields kept)
- [x] Re-run every view gate the registry feeds on the rebased branch: `check-engine-skill-gap`, `check-trend-list-matrix`, `check-vram-scope-view`, `check-quant-catalog` green (#2906 owns the regenerated views; this lane re-rendered only `render-engine-skill-gap`, whose committed view embeds the decision reason)
- [x] `make skills-validate` green with `edge0` covered by the decision entry
- [x] File the folder-format model-pack serving issue and link it in both directions with #2903 (Not covered in #2903's body, origin line in the new issue) — #2909
- [x] Change-note trio (`agent-wiki/`, `docs/changes.d/`, rendered `CHANGES.md`) green under `check-docs`, plus `lint` / `check-wiring`
- [x] `make openspec-validate NAME=engine-skill-decision-edge0-2903` exits 0 and `make lane-preflight` prints `preflight: OK`
