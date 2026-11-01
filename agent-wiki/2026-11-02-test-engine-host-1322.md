# host-side engine serve loop `make test-engine-host` (issue #1322)

The owner's directive was that host/CI test wiring for engines should be a **make command** the
engine-improver lane runs on the host, for each arch-at-a-time that the host supports, against each
engine's smallest model, proving an llm-local answer and measuring tokens/sec — and that the
engine-build pipeline's LAST step run the same command on the CI runner.

`make check-wiring` already proved a script is not a CI gate; nothing drove "serve the engine on
this host and prove it answers". This change makes the host a real caller.

## What `make test-engine-host` does

1. Loads the engine list from the **committed params** (`containers/engines/params/*.json`) — the
   same single source the build matrix uses, never a hard-coded roster.
2. Filters to the engines whose **arch type this host supports**: cuda when `nvidia-smi` reports
   compute caps, rocm when `rocminfo` reports gfx targets, vulkan when a GPU render node exists,
   cpu always — all via `nvidia_compute_caps()` / `rocm_gfx_targets()` in `scripts/engine_skills.py`.
3. Serves **one engine at a time** (a serial loop, never parallel interference).
4. Per engine: **pulls the AS-PUBLISHED image** (`engine_image.pull_published`, never builds a local
   image), serves its **smallest supported model** (the repository's single smallest-model-per-format
   table), **asserts an llm-local `/v1/chat/completions` answer**, and reports the **measured t/s** a
   real run produced (`timings.prompt_per_second` / `predicted_per_second` or the engine's own usage
   field; never a fabricated bench).
5. The per-engine **max-performance input** (contexts/slots, kv-quant, offload, flash-attn, moe —
   whatever the skill already generates) is **read from the generated params** via
   `engine_image.resolve`, never a second hard-coded copy.

## The engine-build workflow's last step

The engine-build workflow's last step now runs the same `make test-engine-host` per engine x arch
row it publishes, so a build that publishes an engine that cannot serve proves it on the runner. On
a GPU-less runner (no nvidia caps, no rocm targets) the GPU legs are **skipped with a documented
reason** (issue #1240) and never redden; cpu legs always run.

## Wiring, not a weakened gate

`scripts/engine_host_test.py` is wired to `test-engine-host` (the target's recipe and the workflow
step), so `make check-wiring` sees it as **real calling** — the host-only position is the command
being the caller, not roster silence. No gate weakened: a directly-attempted supported engine that
cannot serve fails the run. Manifest/roster assertions use subset checks (`expected <= set(actual)`),
never an exact-equality list, so the next engine addition does not redden the guard.

## Verification

- `scripts/engine_host_test.py` unit tests: `tests/test_engine_host.py` (7 passed) — the host-arch
  grid, the t/s reader, the subset engine-list, and the loud-failure path.
- `make check-wiring` green (317 docs); `make check-docs` green; `make openspec-validate
  NAME=test-engine-host` valid.
- Real host serve: `make test-engine-host ENGINE=llama.cpp HOST_ARCH=cpu` served the published
  image, answered llm-local and reported the measured t/s on a real card.
