# 2026-11-04 — engine builds gate on the engine binary; serving is the --serve tier (#1717)

Issue #1717 (market-engine build contract): an engine BUILD should prove the engine **binary**
works (`-h` / `--version`, exit 0 + non-empty output) — deterministic and near-instant — rather than
that a served OpenAI endpoint came up within a 1200 s readiness budget on a specific runner. Before
this change the engine-build smoke validated an engine ONLY by serving it, so a vllm-cpu cell reddened
with `[engine-image] FAIL llgenie-smoke-vllm-cpu not ready after 1200s` (run 41872109802 / job
126721926808) for reasons unrelated to whether the binary was correctly built.

- **`scripts/engine_smoke.py`** gains `binary_smoke()`: the engine binary is invoked with the
  version/help flags it documents (exit 0 + non-empty output) BEFORE any serving. image path runs the
  binary inside the built image (`docker run --rm <tag> <binary> <flag>`); `probe: device` variants
  (vllm cuda/rocm) skip here (device needed at startup, #106) and answer via `detect` in the serve
  tier. skill path probes the installed binary with the launch prelude.
- A new `--serve` flag makes serving conformance the explicit opt-in tier: the DEFAULT
  (`no --serve`) is the engine binary smoke only — never a serving-readiness wait. `--serve` adds the
  image run / OpenAI-SDK contract. No coverage is lost — it is just not the default build gate.
- **`Makefile`**: `test-engine` is the binary-smoke default; new `test-engine-serve` runs the `--serve`
  tier; the push serve-leg (`test-published-engine`) opts in with `--serve` so the AS-PUBLISHED image
  still serves. `test-engine-stage TEST=serve` = the engine binary smoke (never a 1200 s wait).
- **`.github/workflows/engine-build.yml`** verify-step comments updated to the binary-smoke default.
- **`docs/ENGINES.md`** / `docs/ARCHITECTURE.md` describe the binary-smoke default and the `--serve` tier.

The engine matrix cells are unchanged (`serve` for cpu, `detect` for GPU); only what `TEST=serve`
*means* changed.

Implements issue #1717 (PR #1719).
