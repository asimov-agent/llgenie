Fixes #1322

## Summary

`make test-engine-host` — the command the engine-improver lane runs on the host (and the engine-build workflow's LAST step). It loads the engine list from the committed params, filters to the engines whose **arch type this host supports** (cuda via `nvidia-smi` caps, rocm via `rocminfo` targets, cpu always), and serves each **one at a time** against its **smallest supported model** — pulling the AS-PUBLISHED image (never building), asserting an llm-local `/v1/chat/completions` answer, and reporting the **measured t/s** a real run produced.

## What changed

- **`make test-engine-host`** (`.PHONY`) → `scripts/engine_host_test.py`:
  - engine list from `containers/engines/params/*.json` (the single source the build matrix uses);
  - arch filter reuses `nvidia_compute_caps()` / `rocm_gfx_targets()` in `scripts/engine_skills.py`;
  - serves ONE engine at a time (serial loop);
  - pulls AS-PUBLISHED via `engine_image.pull_published` (never build), smallest model per format;
  - asserts llm-local and reports `timings.prompt_per_second`/`predicted_per_second` (or the engine's own usage field) — never a fabricated bench;
  - max-perf input (`variants.<arch>.launch`) **read from the generated params** via `engine_image.resolve`, never a second hard-coded copy.
- **engine-build.yml last step**: runs the same `make test-engine-host` per published row; a GPU-less runner skips the GPU legs with the #1240 reason and never reddens.
- **Wiring**: `scripts/engine_host_test.py` is wired to the target + the workflow, so `make check-wiring` sees it as real calling (no gate weakened); host-only exceptions use subset checks.
- **Docs**: `docs/ENGINES.md`, `docs/BOTS.md`, `CHANGES.md` + `docs/changes.d/` + `agent-wiki/` records.
- **OpenSpec**: `openspec/changes/test-engine-host/` (proposal + targeted spec + tasks) — `make openspec-validate NAME=test-engine-host` exits 0.

## Real measured t/s (this host)

`make test-engine-host ENGINE=llama.cpp` (published images pulled, not built):

- `llama.cpp/cpu`  — **prompt 522.86 tok/s, predicted 74.02 tok/s**
- `llama.cpp/cuda` — **prompt 2766.76 tok/s, predicted 548.41 tok/s**

(both `OK llm-local answered`; the full host sweep across all host-arch-supported engines was launched for the report)

## Out of scope (per the issue)

No engine image built locally (CI builds/publishes); merge policy / auto-merge arm / owner-gate untouched; tester fold-live-profile and docs-fold lanes untouched; #1092 / #91 scope not altered — this is the HOST VERIFICATION RUNNER.

---
AGENTS: branched from fresh `origin/main` **e70df0447c406f4d997f9ed5c0af3f6a8ec571d9** (re-fetched at start of work; tip at commit time)

