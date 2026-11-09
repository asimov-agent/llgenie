# fix(engine): engine-build gates only the binary (-h/--version); serving is host-only

Issue: [#2319](https://github.com/asimov-agent/llgenie/issues/2319) · PR: #2320

## Why

The `engine-build` CI pipeline ran heavy inference-serving tests as a build gate.
A vllm/cpu cell failed the old `serve-leg` with `llgenie-smoke-vllm-cpu not ready
after 600s` — the container warmed up fully (AOT compile 142s, weights loaded, KV
cache allocated) but the `shm_broadcast` block never answered within the 600s budget
(six `No available shared memory broadcast block found in 60 seconds` lines). A slow,
flaky serve-readiness wait is the wrong gate for *whether the build is correct*; the
binary-level checks in the same run all passed.

Owner directive (2026-11-09, verbatim): "we cant do some heavy intense inference
server testing anymore, just check that the binary works for make engine build... the
serving test only executed on the host by the llgenie engine improver manually by a
make command." Narrowed: "we can only test the binary with -h/--version nothing else."

## What Changes

- `.github/workflows/engine-build.yml` — remove the `serve-leg`
  (`make test-published-engine` serving the image and answering "hi") and the
  `host-verify MATRIX` (`make test-engine-host` parallel serve) steps, plus the
  `model` dispatch input that fed them and the `capability/served_arch` decision.
  Per row CI now runs: build → verify (binary) → bind-proof → push-engine →
  **published-binary-leg** (pull the just-published image, verify the engine BINARY
  answers `-h`/`--version`, never starts a server) → install-leg. Dispatch inputs are
  now `engine`/`arch`/`push`/`force`.
- `scripts/engine_smoke.py` — the binary smoke probe set is pinned to exactly
  `["-h", "--version"]` on BOTH paths (image-build and host/skill), ignoring
  `variant_flags`/`documented` extras. So the CI gate tests only those two flags.
- `Makefile test-published-engine` — pull the AS-PUBLISHED image and verify the
  binary answers `-h`/`--version`; the `--serve` chat invocation is removed.
- `TYPED_FLAGS` in `scripts/engine_image.py` stays the full
  `("--version","-h","--help","-V")` (unchanged; the owner confirmed that set is
  still fine) — only what CI probes narrows.
- **Host-only serving stays available**, run by the engine improver one engine at a
  time, never in CI: `make test-engine-host ENGINE=<id> ARCH=<arch> [MODEL=...]` and
  the explicit serve tier `make test-engine-serve ENGINE=<id> ARCH=<arch>`.

## Impact

- `.github/workflows/engine-build.yml` (`serve-leg` + `host-verify MATRIX` removed)
- `scripts/engine_smoke.py` (probe pinned to `-h`/`--version`)
- `Makefile` (`test-published-engine` is binary-only; host serve preserved)
- `tests/test_engine_build_workflow.py`, `tests/test_engine_skills.py`,
  `tests/test_published_gate.py`
- docs trio: `docs/changes.d/2026-11-09-...#2319`, `agent-wiki/2026-11-09-...#2319`,
  `CHANGES.md`
