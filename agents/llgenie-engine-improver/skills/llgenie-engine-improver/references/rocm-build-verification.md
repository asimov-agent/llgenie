# vLLM ROCm build — what to verify when you (or the owner) run it locally

Default rule stands: CI (`.github/workflows/engine-build.yml`) is the sole builder; this host pulls and runs. But the owner may explicitly direct a one-off local `make build-engine ENGINE=vllm ARCH=rocm` for verification. When they do, log EVERY line (tee stdout+stderr to a file, background it, tail it back) and never kill it.

## Fix wiring that must be present (#1696)
Verify these in the generated context `$TMPDIR/llgenie-ctx-*/params.json` BEFORE trusting the build — inspect params.json (read_file/search_files), not the Dockerfile alone:
- Editable vllm install carries `--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match` alongside `-e .` (missing-device-extras fix).
- `triton==3.7.1+git0263a6a6.rocm7.14.0` pin replacing the bare `triton==3.7.1+git0263a6a6` in `requirements/build/rocm.txt`.
- `VLLM_TARGET_DEVICE=rocm` and `PYTORCH_ROCM_ARCH='gfx1030;gfx1100;gfx1101;gfx1102;gfx1151;gfx1200;gfx1201;gfx942'`.

## `Failed to build rocm==0.1.0 … No module named 'poetry'` is a build-backend defect, NOT disk/OOM
The rocm70 fork's editable install pulls `rocm==0.1.0`, whose sdist build backend is `poetry`
(`Call to poetry.core.masonry.api.build_wheel failed`, `× Failed to build rocm==0.1.0`, uv's
`hint: ensure poetry is installed`). Under the `-e .` step's `--no-build-isolation` no build env is
provisioned, so `poetry` is absent and the install dies deterministically — the same cell re-fails on
every rerun. This is a DISTINCT class from a cold-compile SIGKILL (exit 2 `Killed`) or ENOSPC: the log
carries a real `ModuleNotFoundError: No module named 'poetry'` and uv's poetry hint. Fix at the SKILL
(bootstrap step), never a local build: insert a `poetry` install step in the rocm backend's install
chain BEFORE the `uv pip install … -e .` step, then `make generate-engine-params ENGINE=vllm` (params
are generated — hand-editing `params/vllm.json` is reverted by `check-engine-params`). Confirm the
poetry step precedes the `-e .` step in the generated install order, and `check-engine-params` reports
0 stale, before dispatching the single rocm cell. Do NOT chase the poetry defect as disk headroom.

## Prebuilt rocm/vLLM upstream image exists — but caps ~4 releases behind the pin
A source compile is ~40 min cold; the fair alternative to weigh is `FROM` an AMD-published prebuilt
rocM image. Measure it before proposing (do not assume):
```bash
docker manifest inspect docker.io/rocm/vllm:latest   # schemaVersion 2 => exists
curl -s 'https://hub.docker.com/v2/repositories/rocm/vllm/tags?page_size=10&ordering=last_updated'
```
Measured: `docker.io/rocm/vllm` exists and its newest tags bake vLLM **v0.29.0** (rocm10.1/torch 2.13),
while a pinned engine tracks the trending store's newer pin (v0.33.0+) — i.e. the prebuilt base is
**several releases behind** and, crucially, is only a BASE (torch/triton prebuilt); you still `-e .`
our own commit on top, so it is not a zero-build and the poetry bootstrap step stays. `vllm/vllm-openai`
and `ghcr.io/vllm-project/vllm-rocm` had no rocm tag at measurement. So: switching to a prebuilt base is
a **pin-downgrade decision the owner makes**, not a lane optimisation — it trades pin freshness
(the calendar bump cadence) for build wall-clock. Surface it as a choice (keep pin-fresh source-build
≈40 min cold, vs. re-pin to an AMD prebuilt several releases behind) and do not silently lower the pin.

## MAX_JOBS is CUDA-only — its absence on ROCm is CORRECT
Do not flag a missing `MAX_JOBS` on the rocm variant as a defect. The rocm path solves the ROCm clang-20 lack of `--offload-jobs` differently: `CMAKE_HIP_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py`, `CMAKE_CXX_COMPILER_LAUNCHER=...` (same launcher), and `-DCMAKE_JOB_POOLS:STRING=compile=N`. Confirm these appear in the live `cmake /opt/llgenie/engines/vllm/src -G Ninja ...` command. `MAX_JOBS` is the CUDA-side cap only.

## Reading progress on a long build
`engine_image.py build` runs `docker buildx build --progress=plain` and holds buildkit's per-step stream in its own captured output, so the make-level log file stays only a handful of lines (pull/base/inspect/buildx invocation) until steps close — a short log is NOT a stalled build. Judge liveness from the process tree, not the log length:
- `ps aux | grep -E 'buildx|cmake|hip_offload|uv pip|git clone'` — configure/dep-fetch/native-compile stages each show their own child.
- Configure + FETCHCONTENT `git clone` for vllm deps comes first (minutes); the multi-hour pole is the per-arch `hipcc` native compile of the 8 gfx archs.
- Finer real-time detail: `docker ps` for the runc build container, and `/var/lib/docker/buildkit/executor/runc-log.json` for raw exec lines.

Liveness is the `build-engine` STEP's state, not elapsed wall time: query
`gh api repos/<o>/<r>/actions/runs/<id>/jobs` and read the step — `status: in_progress` = alive and
compiling, `conclusion: failure` = real error, `conclusion: cancelled` at ~the cap = the kill class above.
A 40+ min `build-engine` step with every pre-build step green is a healthy cold compile, not a hang.
Size any background watch loop to OUTLAST the build: a `seq 1 60` × `sleep 30` loop (30 min) expires
before a ~40 min cold cell and reports a false `TIMEOUT`; use fewer, longer polls (e.g. `seq 1 40` ×
`sleep 45`) and exit only on `"status":"completed"`. Note GitHub streams a step's log only at completion
— an empty `--log-failed` mid-run means `in_progress`, not a missing log.
