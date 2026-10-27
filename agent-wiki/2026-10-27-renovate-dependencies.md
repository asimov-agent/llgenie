# 2026-10-27 — Renovate owns the pins it can prove are low-risk, and nothing generated

Issue #718 (parent #713). Branch `feat/renovate-dependencies`.

## What was verified

- `make check-renovate` → 0 on this config; each defect it refuses is proven on a fixture in
  `tests/test_renovate_config.py` (9 passed in `llgenie/test:latest`).
- `ci.yml` is asserted to carry **no** `paths:`/`paths-ignore:` on `pull_request` and to declare
  the `engine-image` job — the reason a base-image bump always reaches the image build. Nothing in
  the workflow had to change: it was already unfiltered, and now that property is a gate rather
  than an accident.
- `make check-docs` / `make check-wiring` / `make openspec-validate NAME=renovate-dependencies`
  green; `docs/RENOVATE.md` is linked from `README.md`.

## Decisions

- **`pip-compile` on, `pip_requirements` on the `.in`.** The compiled `tools/requirements*.txt`
  are generated; Renovate edits the `.in` and recompiles, which is the same rule AGENTS.md
  states for humans.
- **Automerge is Python patch/pin/digest only**, with `platformAutomerge: false` and
  `automergeType: pr`. CI's `auto-merge` job remains the single landing authority; a
  container base-image bump never automerges because its build is the review.
- **`github-actions` disabled.** Actions are pinned by `make update-actions` (#719) with a
  reviewed tag diff; an unattended bump is exactly the change that review exists to catch.
- **`ignorePaths` covers every generated file** (`containers/engines/dockerfiles/**`,
  `containers/engines/params/**`, `containers/scanners/digests.json`) and the vendored
  `data/models.json`.
- **The gate treats a path-filtered pipeline as a defect**, not an optimisation: a base-image PR
  that skips `engine-image` would land a base it never built.
- **`prConcurrentLimit`/`prHourlyLimit` and a Monday-05:00 slot** keep Renovate's PRs small and
  out of the weekly `registry-sync` window.

## Status

Implementation complete on the branch; PR open against `asimov-agent/llgenie:main`.
