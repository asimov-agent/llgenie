# A single parity pipeline: same make commands on Linux and macOS, per-OS engine sets, per-engine `make install` proven in its own environment

## Why

The macOS verification pipeline must be literally the same pipeline as the Linux
pipeline — the same `make` commands, in the same order, with the same asserts.
Today the two pipelines already share the `make ci-<job>` targets (issue #117),
but macOS still executes them through the docker test container
(`ENGINE_TEST_RUN`), and neither OS finishes by proving `make install` works
**for each engine that OS supports, in that engine's own environment**.

This change makes the parity contract explicit and complete:

- **Same pipeline on both OSes**, diverging only on the engine matrix (Linux
  builds/tests its container engine images; macOS installs/tests its native-Metal
  engines).
- **Every make command runs its corresponding Python script** (no hidden
  `_install` internal API; the make target is a thin shell entrypoint).
- **`make install` per engine, per environment**: at the end of the pipeline each
  OS runs `make install` for each engine it supports and proves it serves/answers
  — Linux in the docker test container, macOS natively in its own venv/Metal
  environment.
- **bash 5** on macOS as the recipe shell (installed via brew at Makefile init if
  missing, gated by `BASH_VERSION >= 5`), so the same make recipes run identically
  on both OSes.
- **macOS CI never runs a Docker GitHub Action and never starts Colima.** The same
  `make` targets run in the Python 3.11 gguf venv. On an Apple-Silicon Mac, llgenie
  never starts or pulls an engine image: Metal engines run natively, and a
  container-only engine is not offered.
- **No macOS published-image stage and no native-engine CI job.** macOS never runs
  an inference server in a container, so there are no published images to test on
  it (the `macos-published` jobs failed with `docker: command not found`), and
  GitHub's macOS runners have no Metal GPU (`native-engine-macos-arm64` never
  finished). Both jobs are removed; native-Metal engines are proven with
  `make ci-engines BACKEND=metal` on an Apple-Silicon host.

## What Changes

1. A first-class per-OS per-engine install target: given the list of engines the
   current OS supports, run `make install` for each and assert the resulting start
   script reports the engine version and (where the OS/environment can serve)
   answers on the OpenAI endpoint. Hard-fails if any supported engine is skipped.
2. The `make ci-<job>` surface is identical on both OSes (locked by
   tests/test_ci_images.py). The workflows continue to call the same targets; the
   only per-OS difference is which engines are in the install-prove set.
3. macOS Makefile-init ensures bash 5 (brew install if missing, `SHELL` set to it)
   and a `BASH_VERSION >= 5` gate; `python:3.10-slim` -> `python:3.11-slim` in
   the test image with lockfiles recompiled.
4. README/AGENTS.md document the parity contract and the per-engine install proof.

## Success

`make install` is proven for every engine each OS supports, in that engine's own
environment, on both Linux and macOS (`make loop` green on both). `make
openspec-validate NAME=macos-parity-install` passes; every spec scenario names its
test.
