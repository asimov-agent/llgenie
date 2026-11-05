# vLLM ROCm build — what to verify when you (or the owner) run it locally

Default rule stands: CI (`.github/workflows/engine-build.yml`) is the sole builder; this host pulls and runs. But the owner may explicitly direct a one-off local `make build-engine ENGINE=vllm ARCH=rocm` for verification. When they do, log EVERY line (tee stdout+stderr to a file, background it, tail it back) and never kill it.

## Fix wiring that must be present (#1696)
Verify these in the generated context `$TMPDIR/llgenie-ctx-*/params.json` BEFORE trusting the build — inspect params.json (read_file/search_files), not the Dockerfile alone:
- Editable vllm install carries `--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match` alongside `-e .` (missing-device-extras fix).
- `triton==3.7.1+git0263a6a6.rocm7.14.0` pin replacing the bare `triton==3.7.1+git0263a6a6` in `requirements/build/rocm.txt`.
- `VLLM_TARGET_DEVICE=rocm` and `PYTORCH_ROCM_ARCH='gfx1030;gfx1100;gfx1101;gfx1102;gfx1151;gfx1200;gfx1201;gfx942'`.

## MAX_JOBS is CUDA-only — its absence on ROCm is CORRECT
Do not flag a missing `MAX_JOBS` on the rocm variant as a defect. The rocm path solves the ROCm clang-20 lack of `--offload-jobs` differently: `CMAKE_HIP_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py`, `CMAKE_CXX_COMPILER_LAUNCHER=...` (same launcher), and `-DCMAKE_JOB_POOLS:STRING=compile=N`. Confirm these appear in the live `cmake /opt/llgenie/engines/vllm/src -G Ninja ...` command. `MAX_JOBS` is the CUDA-side cap only.

## Reading progress on a long build
`engine_image.py build` runs `docker buildx build --progress=plain` and holds buildkit's per-step stream in its own captured output, so the make-level log file stays only a handful of lines (pull/base/inspect/buildx invocation) until steps close — a short log is NOT a stalled build. Judge liveness from the process tree, not the log length:
- `ps aux | grep -E 'buildx|cmake|hip_offload|uv pip|git clone'` — configure/dep-fetch/native-compile stages each show their own child.
- Configure + FETCHCONTENT `git clone` for vllm deps comes first (minutes); the multi-hour pole is the per-arch `hipcc` native compile of the 8 gfx archs.
- Finer real-time detail: `docker ps` for the runc build container, and `/var/lib/docker/buildkit/executor/runc-log.json` for raw exec lines.
