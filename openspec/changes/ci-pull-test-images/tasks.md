## 1. CI images on GHCR

- [x] 1.1 `scripts/ci_images.py`: hash tag from the inputs, `ref`, `pull` (strict), `ensure` (pull, else local build), `publish` (look up, else two-arch buildx push with registry cache)
- [x] 1.2 Makefile: `test-image` / `openspec-image` -> `ensure`, `test-image-pull` / `openspec-image-pull` -> `pull`, `publish-ci-images`, `ci-image-refs`
- [x] 1.3 CI job `ci-images` (Linux, every push run): GHCR login, QEMU + buildx, `make publish-ci-images`

## 2. Every CI job pulls

- [x] 2.1 `pipeline.yml`, `published.yml`, `engine-image`, `engine-published-test`: `make test-image-pull` / `make openspec-image-pull` instead of building; GHCR read login; `needs: ci-images`

## 3. macOS layout

- [x] 3.1 Makefile `ci-<job>` targets (lint, unit, cron, watch-report, dispatch-e2e, agents-read, openspec, cpu-health, top-tier, install); the cron and watch-report shell checks move from the workflow into them unchanged
- [x] 3.2 `pipeline.yml` (Linux, one job per target, same check names) + `pipeline-macos.yml` (macOS `checks` + `serve` + `install`, every step `if: ${{ !cancelled() }}`); no job of either file has an `if:`
- [x] 3.3 No job or step is skipped in a push run that has engines to build: `make ci-free-disk` and `make test-engine-stage TEST=serve|detect` replace the `runner.os` / `matrix.test` / `env.PUBLISH` step conditions. A PR that changes no engine params emits one `engine: none` row (an empty include list fails the workflow); that row is skipped and builds nothing.

## 4. Tests and docs

- [x] 4.1 `tests/test_ci_images.py` (every scenario), update the workflow tests in `test_macos_install.py`, `test_ci_variant_matrix.py`, `test_engine_skills.py`
- [x] 4.2 README CI section + AGENTS.md Makefile target list
- [x] 4.3 Local: `make test-unit`, `make lint`, `make openspec-validate NAME=ci-pull-test-images`, `make test-image` / `make openspec-image` and the `ci-*` targets the pipeline runs

## 5. Verified live

- [x] 5.1 Push run: `ci-images` published `llgenie/test:<hash>` + `llgenie/openspec:<hash>` (amd64 + arm64) to GHCR; no job built a test image; Linux required checks green
- [x] 5.2 Before/after macOS wall time measured and reported on the PR and the issue
