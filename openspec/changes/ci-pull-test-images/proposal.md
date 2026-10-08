# CI pulls its test images from GHCR; macOS boots Docker 3 times, not 10

Issue: [#117](https://github.com/asimov-agent/llgenie/issues/117)

## Why

CI spends most of its time building the same two test images over and over.

- **macOS (run 37834044344):** every macOS job boots its own Docker VM (docker/setup-docker-action, a Lima vz VM) for 5–10 min, then builds `llgenie/test` from scratch for 4–8 min, before a make target that often takes seconds. For example, `macos / lint` spent 576 s booting and 470 s building for a 12 s `make lint`.
- **macOS queueing:** GitHub runs only a few macOS jobs at a time per account, so ten macOS pipeline jobs plus four install-published jobs queue behind each other.
- **Linux:** every `engine-image-*` and `test-published-*` job (~37 each) runs `make test-image` before its tests, and `openspec` builds `llgenie/openspec` in every run.

## What Changes

- **Content-addressed CI images on GHCR.** New `scripts/ci_images.py`. The tag is a hash of each image's inputs:
  - `llgenie/test`: `containers/test/Dockerfile`, `tools/requirements.txt`, `tools/requirements-dev.txt`;
  - `llgenie/openspec`: `openspec/Dockerfile`.

  The published ref is `<LLGENIE_REGISTRY>/llgenie/<name>:<hash>`, e.g. `ghcr.io/asimov-agent/llgenie/test:3f2a…`. The build context is a temp dir that holds exactly those inputs.
- **`make publish-ci-images` (CI job `ci-images`, Linux, every push run):** for each image whose hash tag is not on GHCR yet, a multi-arch buildx build (linux/amd64 + linux/arm64, for Linux and Intel-macOS runners and Apple-Silicon dev hosts) with a registry layer cache, pushed. An already published hash is a single manifest lookup, with no build.
- **CI jobs pull, never build:**
  - `make test-image-pull` / `make openspec-image-pull` pull the hash tag and tag it as the local `llgenie/test:latest` / `llgenie/openspec:latest` that every make target already uses.
  - A missing tag fails loudly; there is no rebuild in CI.
  - Applies to `pipeline.yml` (Linux + macOS), `published.yml`, `engine-image` and `engine-published-test`, which all `need` `ci-images`.
- **Local `make test-image` / `make openspec-image`** pull the published image for the current hash, and build it from the same Dockerfile only when that hash is not published yet (an edited Dockerfile or lockfile). This is how engine images already work (`engine_image._available`: pulled if published, else built).
- **macOS pipeline in three jobs.**
  - Every pipeline job's steps become one `make ci-<job>` target (`ci-lint`, `ci-unit`, `ci-cron`, `ci-watch-report`, `ci-dispatch-e2e`, `ci-agents-read`, `ci-openspec`, `ci-cpu-health`, `ci-top-tier`, `ci-install`). The fake-crontab and fake-gh shell checks move from the workflow into the Makefile unchanged.
  - Linux (`pipeline.yml`) keeps one job per target, and keeps its required check names.
  - macOS (`pipeline-macos.yml`) runs the same targets as ordered steps of two jobs, `checks` and `serve`, plus `install`. That is 3 Docker-VM boots and 3 test-image pulls instead of 10 boots and 9 builds. Every step runs even when an earlier one failed (`if: ${{ !cancelled() }}`), so each target still reports.
- **No CI job or step is skipped.** Each OS has its own pipeline file, so neither shows the other's jobs as skipped. Steps that were skipped by a condition now always run, and make decides inside:
  - `make ci-free-disk` frees disk on a Linux runner and reports only on macOS;
  - `make test-engine-stage TEST=serve|detect` is the one post-build test step for every engine image;
  - the GHCR login, uv and hf CLI steps run in every engine-image job;
  - `macos-published` keeps running on every push.
- **Docs:** README CI section and the AGENTS.md Makefile target list.

Out of scope: renaming `scripts/llama_serve.py`.

## Impact

- Code: `scripts/ci_images.py` (new), `Makefile`, `.github/workflows/{ci,pipeline,published}.yml`, `.github/workflows/pipeline-macos.yml` (new), `.github/actions/docker/action.yml`.
- Tests: `tests/test_ci_images.py` (new); updated `tests/test_macos_install.py`, `tests/test_ci_variant_matrix.py`, `tests/test_engine_skills.py`.
- Registry: new GHCR packages `llgenie/test` and `llgenie/openspec` next to the engine images.
