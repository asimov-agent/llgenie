# engine(host): a parameterized make command that serves one engine's published image against a MODEL on the host (sequential) and as the engine-build pipeline's last step (a parallel matrix over the runner's supported cells), proving an llm-local answer + measured t/s

## Why

The host-side test wiring for engines is only marginally wired (`make check-wiring` proves a
script is not a CI gate but nothing drives "serve the engine on this host and prove it answers").
The owner directive (refined): a make command the engine-improver lane runs ON THIS HOST, serving
**one engine** (`ENGINE=<id> ARCH=<arch> MODEL=<model>`) — the parameterized form selects what is
served. It is used TWO ways: (a) **CI / build-publish** — the pipeline's LAST step runs the same
parameterized commands as a **parallel matrix** over the supported (engine × arch) cells, keyed off
the arch types the GitHub Actions runner itself supports at runtime; (b) **host / local** — the
engine-improver lane drives the same command **one engine at a time** (sequential, never parallel —
engines contend for the GPU). It asserts an llm-local answer and reports a measured throughput.

This makes the host-only-wiring entry a REAL caller (the command IS the caller; `make check-wiring`
still fails a script wired to nothing), and turns the engine-build last step from "the image
answers a flag" into "the image was actually served against a model and answered".

## What becomes true

- `make test-engine-host` **exists** (a real `.PHONY` target), parameterized as
  `ENGINE=<id> ARCH=<arch> MODEL=<model>` — the owner-refined form. `MODEL` is the LLM model to
  serve with (already fits host VRAM and the engine supports it); when omitted, the engine's
  smallest supported model (the repository's single smallest-model-per-format table) is served.
  The engine list and each engine's tuning come from the **committed params**
  (`containers/engines/params/*.json` — the same single source the build matrix uses), and the
  supported arch set is filtered by `nvidia_compute_caps()` / `rocm_gfx_targets()` in
  `scripts/engine_skills.py` (cpu always; vulkan where a GPU render node exists).
- **CI usage — parallel matrix on the runner's arch types:** the engine-build workflow's LAST step
  runs the same parameterized commands as a matrix over the supported (engine × arch) cells IN
  PARALLEL (max-parallel), one element per cell, with the supported set keyed off the arch types
  the GitHub Actions runner itself supports (checked at runtime on the runner via the shared
  `nvidia_compute_caps()`/`rocm_gfx_targets()` reuse — never the dev host's arch). A GPU-less runner
  skips the GPU legs with a documented reason (issue #1240) and never reddens them.
- **Host usage — sequential one engine at a time:** the lane drives the same command one at a time
  (directly or via a thin sequential wrapper), never parallel on the host. `MODEL` is threaded
  through to the serve.
- Per engine, the command **serves the published image** (pull AS-PUBLISHED via
  `engine_image.pull_published`, never build) against the given MODEL, **asserts an llm-local
  answer** (a real `/v1/chat/completions` with a non-empty message), and reports a **measured
  throughput** number a real run produced (`timings.prompt_per_second` / `timings.predicted_per_second`,
  or the engine's own t/s usage field; never a fabricated bench).
- A **parameters list per engine** documents the input to run it at max performance (the flags the
  skill already generates: contexts/slots, kv-quant, offload, flash-attn, moe) — the command
  **reads these from the generated params** (`variants.<arch>.launch`/`env` via
  `engine_image.resolve()`), never a hard-coded second copy.
- The **host-only-wiring.json** position for this is made TRUE wiring: the command is the caller
  (the script is wired to `test-engine-host`, which `check-wiring` sees, and the workflow matrix
  step calls the same target). **No gate is weakened** — `make check-wiring` still fails a script
  wired to nothing.
- Manifest/roster assertions use **subset checks** (`expected <= set(actual)`), never exact-equality
  lists.

## Not covered

- Building engine images locally (CI builds and publishes; this host and the runner only pull and run).
- Changing merge policy, auto-merge arm semantics, or the owner-gated review gate (#1088).
- The tester lane's fold-live-profile wiring; the docs fold lane.
- Altering #1092 (hardware pair OFFER) or #91 (serving-flag audit) scope — this is the HOST
  VERIFICATION RUNNER those consume, and it reads whatever max-perf structure their params carry.
