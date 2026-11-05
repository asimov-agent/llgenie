# vLLM/vs. ROCm `-e .` HIP/CMake detection defect (issue #1365)

## Symptom (surfaced by `--progress=plain` + `_sh` stdout printing, run 41342311363)

- **rocm**: `Optional package HIP not found` / `No FindHIP.cmake in CMAKE_MODULE_PATH`, from torch's `LoadHIP.cmake` after the pip `rocm-sdk-core` install. CMake picks the pip wheel's `_rocm_sdk_core` directory as the ROCm root instead of the base image's `/opt/rocm`.
- **cpu**: `csrc/.../utils.cpp:2: fatal error: numa.h: No such file or directory` — CPU backend needs `libnuma-dev` (numactl headers) in the base.
- **cuda**: `make build-engine ... Killed` exit 143 (SIGTERM) — the compile exceeds the **hosted ubuntu-24.04 runner** memory; needs the large/self-hosted runner, not a code fix.

## Fixes that landed (skill `skills/engines/vllm/SKILL.md`, regenerated into `containers/engines/params/vllm.json`)

```
# rocm -e . step: point HIP at the base image's /opt/rocm
ROCM_HOME=/opt/rocm ROCM_PATH=/opt/rocm HIP_PATH=/opt/rocm \
  CMAKE_ARGS='-DROCM_PATH=/opt/rocm -DCMAKE_PREFIX_PATH=/opt/rocm \
    -DCMAKE_MODULE_PATH=/opt/rocm/lib/cmake/hip;/opt/rocm/lib/cmake/hip-lang' \
  PYTORCH_ROCM_ARCH='{gpu_targets}' VLLM_TARGET_DEVICE=rocm \
  uv pip install --system --break-system-packages --no-build-isolation -e .
```

```
# cpu container apt: add the numa headers
apt: [python3-dev, libnuma-dev]
```

## Reusable rules

- **Fix at the skill, then regenerate the params JSON.** `containers/engines/params/*.json` is a generated artifact (`scripts/engine_skills.py params --only <engine>`) — never hand-edit it; the hash-injected tag shift follows the skill change automatically.
- **rocm pip-installed SDK layout differs from the system ROCm.** Point `ROCM_PATH`/`ROCM_HOME`/`HIP_PATH`/`CMAKE_MODULE_PATH` at the base's `/opt/rocm` (which ships `hipcc` + FindHIP); never assume the pip wheel root carries the HIP cmake configs.
- **SIGTERM `Killed` from a docker build is a runner-resource signal**, not a build-defect — classify it as a runner-capability issue (matrix label / self-hosted) before blaming the Dockerfile.
- **Diff the real layer error, not the outer FAIL.** The `_sh` (child stdout/stderr on non-zero rc) + `--progress=plain` pair is what finally surfaced these three per-cell errors after runs that only showed `make build-engine` fail silently.
- A single fix can be necessary-not-sufficient: each arch cell is its own build path (rocm≠cuda≠cpu) — verify every cell's job log, not just the first one that turns green.
