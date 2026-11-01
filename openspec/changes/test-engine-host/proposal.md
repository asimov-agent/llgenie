# engine(host): a make command that serves each supported-arch engine's smallest model on the host (and as the engine-build last step) and proves an llm-local answer + measured t/s

## Why

The host-side test wiring for engines is only marginally wired (`make check-wiring` proves a
script is not a CI gate but nothing drives "serve the engine on this host and prove it answers").
The owner directive: a make command the engine-improver lane runs ON THIS HOST, which serves each
engine's published image against the **smallest model** that engine supports and that fits host
VRAM, **one engine at a time**, only for engines whose **arch type this host supports**, asserts an
llm-local answer, and reports a measured throughput. The engine-build pipeline's **last step must
run the same command** on the CI runner for every host-arch-supported engine with its smallest
supported model.

This makes the host-only-wiring entry a REAL caller (the command IS the caller; `make check-wiring`
still fails a script wired to nothing), and turns the engine-build last step from "the image
answers a flag" into "the image was actually served against a model and answered".

## What becomes true

- `make test-engine-host` **exists** (a real `.PHONY` target) and loads the engine list from the
  committed params (`containers/engines/params/*.json` — the same single source the build matrix
  uses), filters to **engines this host's arch type supports** (reuse `nvidia_compute_caps()` /
  `rocm_gfx_targets()` in `scripts/engine_skills.py` for cuda/rocm; cpu always; vulkan where a GPU
  render node exists), and serves **one engine at a time** (a serial loop, never parallel).
- Per engine, the command **serves the published image** (pull AS-PUBLISHED via
  `engine_image.pull_published`, never build), with the engine's **smallest supported model** that
  fits host VRAM (the repository's single smallest-model-per-format table),
  **asserts an llm-local answer** (a real `/v1/chat/completions` with a non-empty message), and
  reports a **measured throughput** number a real run produced (`timings.prompt_per_second` /
  `timings.predicted_per_second`, or the engine's own t/s usage field; never a fabricated bench).
- A **parameters list per engine** documents the input to run it at max performance (the flags the
  skill already generates: contexts/slots, kv-quant, offload, flash-attn, moe) — the command
  **reads these from the generated params** (`variants.<arch>.launch`/`env` via
  `engine_image.resolve()`), never a hard-coded second copy.
- The **engine-build workflow's LAST step** invokes the same command on the CI runner over every
  host-arch-supported engine with its smallest supported model — a build that publishes an engine
  that cannot serve proves it on the runner. A **GPU-less runner skips the GPU legs with a documented
  reason** (issue #1240) and never reddens them.
- The **host-only-wiring.json** position for this is made TRUE wiring: the command is the caller
  (the script is wired to `test-engine-host`, which `check-wiring` sees, and the workflow step calls
  the same target). **No gate is weakened** — `make check-wiring` still fails a script wired to nothing.
- Manifest/roster assertions use **subset checks** (`expected <= set(actual)`), never exact-equality
  lists.

## Not covered

- Building engine images locally (CI builds and publishes; this host and the runner only pull and run).
- Changing merge policy, auto-merge arm semantics, or the owner-gated review gate (#1088).
- The tester lane's fold-live-profile wiring; the docs fold lane.
- Altering #1092 (hardware pair OFFER) or #91 (serving-flag audit) scope — this is the HOST
  VERIFICATION RUNNER those consume, and it reads whatever max-perf structure their params carry.
