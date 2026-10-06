# One agent skill per inference server (issue #98)

## Why

The trending-local-llms index (`data/models.json`, `engines{}`) lists 16 inference
servers. Each one installs differently, and the right build depends on the hardware:
CUDA arch from `nvidia-smi compute_cap`, ROCm `gfx` target from `rocminfo`,
CUDA 12 vs 13 wheels, Metal vs CPU. Some are not HTTP servers at all (WebLLM runs in
the browser, DFlash2 is a drafter, MLX-fast is a benchmark harness). Hard-coding
this in Python or shell rots as soon as upstream renames a flag. For example,
`LLAMA_CUBLAS` is now a FATAL_ERROR shim and `AMDGPU_TARGETS` became `GPU_TARGETS`.
`build_llama_server.sh` and `detect_server.py` still passed `-DLLAMA_CUBLAS=OFF` and
cloned `ggerganov/llama.cpp`.

Parent: #92. Unblocks #94, #99, #100 and #91.

## What Changes

- Add `skills/engines/<id>/SKILL.md` for **every** engine in the registry (16). Each
  skill has machine-readable YAML front matter (repo, tracked ref, pinned sha,
  backends, OS, formats/quants, prereqs, per-backend install steps,
  **hardware-derived flags**, hardware floors, env, binary, detect, launch, health,
  alias mode, upstream drift-watch files) and a human body (hardware table,
  renamed options, pitfalls). Every fact was read from the engine's upstream repo at
  the pinned sha or tag.
- Add `servable: true | false | via`. Non-servers are never installed. `via` names the
  host engines that serve the model instead (DFlash2 -> sglang; MLX-fast -> tensorfold, mlx).
- Add `scripts/engine_skills.py`, a stdlib-only generic runner. It detects hardware
  parameters (`compute_cap`, `cuda_arch`, `cuda_version`/`cuda_major`, `gpu_targets`,
  os/arch, jobs, with env seams for CI), renders a skill for this machine, checks
  floors and prereqs (reporting the exact blocker), validates skills against the
  registry, and runs installs. It contains no engine-specific install code.
- Migrate llama.cpp + Prism first. `build_llama_server.sh` takes repo URL, branch,
  clone dir, build dir and cmake flags from `engine_skills.py build-env`, and
  `detect_server.py` reads URL/branch from the skills. A CUDA build now targets the
  detected arch (`-DCMAKE_CUDA_ARCHITECTURES=89` on an RTX 4090 Laptop) and omits it
  when no GPU is visible (CI). `-DLLAMA_CUBLAS=OFF` is gone. Upstream clones from `ggml-org`.
- Add make targets `skills-validate`, `engine-list`, `engine-hardware`, `engine-plan`,
  `engine-check`, `engine-install` and `engine-detect`. Add `make skills-validate` to CI
  and `tests/test_engine_skills.py` to `make test-unit`.
- Engines are installed **only inside their container image**, built with `make build-engine`
  from frozen per-arch params (`make generate-engine-params`), and run with `make run-engine`.
  There are no host venvs. Python engines use `uv pip install --system` in the image. Only Metal
  (no containers) installs natively with `uv tool install`. No sudo, no `curl | sh`. The Ollama
  tarball is checked against the release `sha256sum.txt` before it is extracted.

- **Images, per engine x backend (29):** `make generate-engine-params` (the only step that
  reads skills) writes frozen params, one Dockerfile per engine x backend and 4 shared bases.
  Official images are the bases where they exist; compiled engines build on the shared base or
  a pinned upstream runtime (the ROCm source builds on `rocm/pytorch` 7.2.4).
- **CI, two matrices:** `engine-image` builds each image, tests it (cpu: serves and answers
  "hi" on the OpenAI API; GPU: version), and on every push run publishes it to the repo's
  GHCR (feature branches too, for now). The second matrix `engine-published-test`
  (`test-published-<engine>-<arch>`) pulls every published image on a fresh runner, checks
  digest and version, starts the container and chats "hi" (GPU images on CPU), and installs
  it from the registry only (#102).
- **`make install` is container-only and pulls only this host's tested images:** it detects
  the backend and pulls the published images for it (never builds by default), the
  llama.cpp core first; other engines are pulled on first use by `llgenie --pick/--engine`.
  Start scripts `~/bin/llgenie-engine-<id>` plus the shims `~/bin/llama-server` (stock
  llama.cpp image) and `~/bin/prism-server` (Prism image); CI tests this last, per
  backend, against the published images (`install-published`);
  cuda uses the host driver through CDI; `make test-built-engine` checks every version;
  `make uninstall` removes exactly what install wrote. Only Metal builds natively.

## Impact

- `scripts/engine_skills.py` (new), `skills/engines/*/SKILL.md` (new, 16),
  `skills/engines/README.md` (new), `scripts/build_llama_server.sh`,
  `scripts/detect_server.py`, `Makefile`, `.github/workflows/ci.yml`, `README.md`,
  `tests/test_engine_skills.py` (new), `tests/test_detect_server.py`,
  `tests/fixtures/trending-models.json` (new pinned registry snapshot).
- `containers/engines/` (params, Dockerfiles, bases, entrypoint), `containers/test/Dockerfile`,
  `scripts/engine_image.py`, `scripts/engine_smoke.py`, `scripts/engine_runner.py`,
  `scripts/install_engine_launchers.py`, `scripts/llama_serve.py` (server resolution),
  `tests/test_engine_runs.py`, `tests/test_engine_version.py`, `AGENTS.md`.
- `make install` no longer builds llama.cpp on Linux: it installs the engine images and
  shims. `make build-variant` stays for the native macOS Metal builds. The Linux
  `server-variants` CI job is replaced by the engine-image matrix; the macOS variants stay.
