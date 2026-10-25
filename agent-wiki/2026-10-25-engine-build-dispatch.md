# 2026-10-25 — a dispatched sweep that builds every engine at its pin

Issue: [#614](https://github.com/asimov-agent/llgenie/issues/614)
OpenSpec: `openspec/changes/engine-build-dispatch`
Related: [#615](https://github.com/asimov-agent/llgenie/issues/615) (every variant from source)

## What changed

`ci.yml` builds only the images a PR changed (`CHANGED=<base>`), so no run ever exercised the whole
pinned set. `.github/workflows/engine-build.yml` is now the independent sweep: `workflow_dispatch`
only (`engine`, `arch`, `push`), guard job first, a matrix from `make engine-build-matrix`, and one
`build` job per row running `make build-engine` then `make test-engine-stage` in the row's mode
(`serve` for cpu, `detect` for GPU). It never runs on a PR, a push or a schedule. Each row is built, **then verified, then**
published — `make push-engine` is its own gated step that re-checks the binary's flags, so a
failing binary never reaches GHCR.

`scripts/engine_image.py matrix` gained `--engine` / `--arch`, and `make engine-build-matrix` wraps
it, so the rows are `containers/engines/params/*.json` — 27 CI rows today — never a roster.

## Decisions

- **One matrixed workflow, not one YAML per engine.** The dispatch form, the guard and the README
  row live in one place, and a new engine variant enters the sweep when its params are committed.
- **"From source" is now a checked claim.** `make check-engine-source`
  (`scripts/engine_source_guard.py`, in `ci-unit`) reads the committed params and fails when a cell
  says `prebuilt: false` but its `install` steps only download a wheel or a release archive. Census
  today: 31 cells — 22 `prebuilt: false`, 9 `prebuilt: true`; of the 22, **17 run a real build and 5
  are tracked exceptions** in `KNOWN_NOT_SOURCE` (freetoken/cuda, litert/cpu, mlx cpu+cuda install a
  wheel; tensorfold/cuda downloads the upstream release tarball) — issue #615. Converting a cell
  means deleting its exception entry.
- **A serving cell proves its binary first.** `make test-engine-stage TEST=serve` runs
  `make test-engine-image` (flags) and only then `make test-engine`, joined with `&&`; previously a
  cpu row went straight to serving, so its binary was never probed.
- **A CLI with no version flag is not a failure.** `binary_probe: help` (mlx cpu, sglang cuda/rocm)
  requires the help family and takes the version from the image's `detect`; found by this sweep
  running the whole matrix.
- **`ci.yml` keeps its changed-images gate.** Removing it is not part of this change: it is what
  stops an unbuildable engine bump from merging. The sweep is additive and on demand.
- **The sweep builds whatever the params say.** `prebuilt: true` variants start `FROM` an upstream
  image; `prebuilt: false` variants compile. `llama.cpp` was converted to source builds in all four
  variants here (its skill already had the compile steps; only the `container:` block pointed at the
  official images). 12 variants remain prebuilt (ollama ×4, vllm ×3, sglang cuda, tensorrt-llm cuda)
  — issue #615.

## Verified

- `make check-workflows` — the new YAML parses, ends with a newline, has a top-level name.
- `make check-dispatch-forms` — 14 dispatchable workflows, the README table carries `engine-build.yml`.
- `make check-docs` — 195 user-facing targets documented (including `engine-build-matrix`).
- `make check-wiring`, `make lint`, `make openspec-validate NAME=engine-build-dispatch`.
- `tests/test_engine_build_workflow.py` — dispatch-only, guard first, matrix from the params,
  every row built and verified, publishing opt-in.
- `make generate-engine-params ENGINE=llama.cpp` then `make build-engine ENGINE=llama.cpp ARCH=cpu`:
  the image is compiled from the pinned sha on the shared devel base (no upstream prebuilt image),
  and `make test-engine-image ENGINE=llama.cpp ARCH=cpu` verifies the binary.
