# vllm v0.32 Rust-frontend build defect — how to diagnose a silent docker buildx failure

## Symptom
`make build-engine ENGINE=vllm ARCH={cpu,rocm,cuda}` in CI: `docker buildx build` runs ~11 min
(source-compile) then exits 1, and the docker output is **gone from the GitHub job log**.
`_sh(cmd)` in `scripts/engine_image.py` CAPTURES docker output (it calls `run_ok`, whose `_cmd` uses
`capture_output=True`) and never prints it, so the error is dropped before it can reach the log; and
even when printed, BuildKit's interactive progress overwrites lines with `\r`, which GitHub's plain-text
log storage collapses. Result: `[engine-image] FAIL build <tag> (exit 1)` with no underlying error
recoverable from the archived job log. **The docker error is unrecoverable from CI logs until `_sh`
prints the captured streams on a non-zero rc — diagnose the recipe statically instead.**

## Root cause (grounded, vllm v0.32.0)
vllm v0.32.0 ships a **vendored Rust frontend `vllm-rs`** (`rust-toolchain.toml` channel `1.95`). Its
`setup.py` `precompiled_build_rust` skips the local cargo build ONLY if both prebuilt
`vllm/vllm-rs` AND `_rust_*.so` artifacts exist; otherwise it warns and calls `super().run()` →
`setuptools-rust` invokes `cargo`. The llgenie recipe (`containers/engines/params/vllm.json`) runs
`uv pip install --no-build-isolation -e .` as the final step with **no Rust toolchain installed**, and
`containers/engines/base/Dockerfile.{cpu,cuda}` install no cargo/rustup/rust → cargo absent → build fails.

Proof keys (run once, don't re-derive):
- clone pinned commit; `rust-toolchain.toml` (channel 1.95) + `setup.py` lines ~489-519
  `precompiled_build_rust` fallback → setuptools-rust → cargo.
- base Dockerfile.{cpu,cuda} apt list: no rust/cargo/rustup (zero refs).
- precompiled `wheels.vllm.ai/<sha>/cpu/vllm/*whl` cp38-abi3 wheels carry only a `vllm/vllm-rs`
  path marker, **no `_rust_*.so`** — so "install a precompiled wheel" cannot satisfy
  `precompiled_build_rust` without `VLLM_USE_PRECOMPILED=1` + real artifacts.
- `docker manifest inspect ghcr.io/<org>/llgenie/vllm:<tag>` rc=1 for ALL tags across heads →
  never-built defect at every head, independent of any pin/hash shift.

## Fix (landed) — mirror upstream `docker/Dockerfile` rust-build stage
In `skills/engines/<engine>/SKILL.md`, add an install step **before** the final `-e .` for EVERY
variant (cpu/cuda/rocm): `cd {src} && bash tools/build_rust.sh` — it bootstraps rustup, installs
channel 1.95 and precompiles `vllm/vllm-rs` + `_rust_*.so`, so `precompiled_build_rust` skips cargo
at `-e .`.

**Edit the SKILL install list, never `params/<engine>.json`** — the params JSON is GENERATED from the
skill (`make generate-engine-params` / `scripts/engine_skills.py params`) and `check-engine-params`
reverts a hand edit. Regenerate, then prove no drift with
`python3 scripts/engine_skills.py params --only <engine> --check` → must read `0 file(s) stale`;
commit the SKILL and the regenerated JSON **together** so the two cannot diverge.

The edit re-shifts the content-addressed tag — a **designed** consequence (the old tag can never
build), so route the new push before editing: commit + push the branch, dispatch `engine-build` at it
with `engine=<id> push=true force=true`, and settle on
`docker manifest inspect ghcr.io/<org>/llgenie/<engine>:<new-tag>` rc=0 (never build locally).

## General rule
A silent long-running `docker buildx build` exit-1 with no archived BuildKit output = the CI log
endpoint cannot show the layer error (the `_sh` wrapper captures the child streams and drops them;
BuildKit carriage-return progress compounds it). Diagnose by reading the engine's build recipe +
upstream build tooling statically, NOT by re-dispatching expecting a better log — and fix the wrapper
(print captured stdout/stderr on non-zero rc) before trusting any future build log.

Refs: engines/vllm SKILL install list, upstream `docker/Dockerfile` rust-build stage, sglang
cmake>=4 marginal-toolchain precedent.
