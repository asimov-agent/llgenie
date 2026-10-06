# feat-engine-skills — Tasks

Checklist of record for issue #98. Ticked the moment the work is verified.

## Research

- [x] 1.1 Read each registry engine's upstream repo at its pinned sha or tag (build docs,
      CMakeLists, pyproject, server CLI source) for backends, per-backend install,
      hardware-derived parameters, launch, alias and health. Recorded in each SKILL.md.

## Skills

- [x] 2.1 `skills/engines/README.md`: format, servable modes, hardware parameters, how to add an engine.
- [x] 2.2 One SKILL.md for each of the 16 registry engines (llama.cpp, Prism fork,
      LaurentZuijdwijk fork, Ollama, vLLM, SGLang, TensorRT-LLM, FreeToken, Strata,
      MLX, TensorFold, LiteRT, MLX-fast Bonsai 2, DFlash2, WebLLM, ExLlamaV3 ROCm fork).

## Runner

- [x] 3.1 `scripts/engine_skills.py`: stdlib YAML-subset parser, hardware detection,
      render, check, validate, install, detect, build-env.
- [x] 3.2 Make targets `skills-validate`, `engine-list`, `engine-hardware`, `engine-plan`,
      `engine-check`, `engine-install`, `engine-detect`.

## Migration

- [x] 4.1 `build_llama_server.sh` evals `scripts/native_build_env.py`, which reads the generated `params/<id>.json` (`native.<backend>`). The hardcoded URLs/flags and `-DLLAMA_CUBLAS=OFF` are gone.
- [x] 4.2 `detect_server.py` reads URL/branch from the generated params. `_find_nvcc` honours the `_which` seam.
- [x] 4.3 Skills are read only by `make generate-engine-params` (plus the inspection targets). Every build path works with `skills/` deleted (tested).

## Tests + CI + docs

- [x] 5.1 `tests/test_engine_skills.py` (one test per scenario, including install idempotency) is in `make test-unit`, together with `tests/test_detect_server.py`.
- [x] 5.2 `make skills-validate` runs in the CI `unit` job.
- [x] 5.4 `make generate-engine-params` freezes each skill into `containers/engines/params/<id>.json` (one variant per backend x GPU arch). `make check-engine-params` runs in CI.
- [x] 5.5 `make build-engine ENGINE= [ARCH=]` builds one image per engine x arch from the frozen params only (`containers/engines/Dockerfile` + `entrypoint.sh` + `scripts/engine_runner.py`). The tag hashes the variant, so there are no rebuilds. `EXPOSE 11434`. `make run-engine` / `stop-engine` / `list-engine-images`.
- [x] 5.9 Base images first: llama.cpp uses the official ggml-org server images (digest-pinned) for cpu/cuda/rocm/vulkan. vllm, ollama, sglang and tensorrt-llm use their official images. The forks, mlx, litert, freetoken and exllamav3 use the shared llgenie base or an upstream runtime (NGC, rocm/pytorch). No image starts from a bare distro. Fixes from the CI macOS jobs: the ollama darwin tgz extracts to bin/, and mlx serves any model name (`alias_mode: any-name`).
- [x] 5.10 Per engine x arch make targets `build-engine-<engine>-<arch>` / `run-engine-<engine>-<arch>`, `build-engines ARCH=`, and the alias `generate-build-engine-params`.
- [x] 5.32 From CI run 37407553595: the published GPU images of vLLM, SGLang, TensorRT-LLM, FreeToken, mlx (cuda) and TensorFold refuse to start without a GPU, so `test-published-engine` chats only with cpu images and CPU_FALLBACK engines (llama.cpp family, Ollama) and gives the others the version test; the registry install step runs with `LLGENIE_NO_GPU=1`. Pre-publish jobs (install, cpu-health, top-tier) build their image (`BUILD=1` / `--build`) because PR runs cannot pull unpublished images.
- [x] 5.31 From CI run 37398159369: llama.cpp-laurentzuijdwijk/cuda (build-time `--help` needs libcuda.so.1) and exllamav3-rocm/rocm (cuda_shim needs torch >= 2.13 headers) failed; llama.cpp-prism cuda/rocm ran > 50 min. All four are in `engine_image.DISABLED` (issue #103): not built, published, installed, offered or tested; Prism falls back to its cpu image on cuda/rocm hosts.
- [x] 5.30 `make install` pulls only the host backend's published images from `ghcr.io/asimov-agent` (never builds unless `BUILD=1`), installs the llama.cpp core by default (`ENGINES=all` for every engine), and llgenie pulls a picked engine on first use (`--ensure`). CI matrix `install-published` (cpu/cuda/rocm/vulkan mocked, last stage after `engine-published-test`) runs `make test-install-published`: pull-only install, "hi" through both shims and through `--pick --engine`, uninstall clean.
- [x] 5.29 AGENTS.md: no git worktrees; all work in the one clone with the feature branch checked out.
- [x] 5.28 ROCm source builds (from CI runs 37388753851 / 37391255349): exllamav3, sglang and freetoken on the pinned `rocm/pytorch:rocm7.2.4…2.10.0` base, installed into its python (`python3 -m pip`, torch constraints from the base); exllamav3 gets a comma-separated RDNA3/3.5/4 list (its setup.py does not split on `;`: hipcc got one bogus `--offload-arch`, "undefined symbol: main"); freetoken pinned to a main commit (ROCm only after v0.1.3), RDNA3/4, torch 2.11 from the PyTorch ROCm 7.2 index; sglang follows upstream `docker/rocm.Dockerfile` (`pyproject_rocm.toml`, `pyproject_other.toml [srt_hip,diffusion_hip]`, rustc/cargo 1.91). Still to prove: a green CI build of these three.
- [x] 5.27 Run args `--shm-size 2g` (vLLM: "Insufficient space in /dev/shm"); vllm/cpu sizes its KV cache with `VLLM_CPU_KVCACHE_SPACE=4` instead of `--gpu-memory-utilization 0.90` (90 % of system RAM). mlx serves `llm-local` via a symlink dir (a request for `llm-local` was looked up on huggingface.co) and the cpu smoke uses the bf16 model (4-bit is minutes per token on MLX CPU). Post-build tests run in `llgenie/test`, built in the engine-image job; top-tier serve keeps its model under the repo-mounted CI home. Verified locally: vllm/cpu, mlx/cpu, llama.cpp/cpu answer "hi".
- [x] 5.26 `make install` writes `~/bin/llama-server` (stock llama.cpp image) and `~/bin/prism-server` (Prism image), each with its image's real llama-server path (Prism has no `/app/llama-server`: CI install failed); llgenie resolves `prism-server` on prism cards and `llama-server` otherwise. Verified locally: both shims answer "hi" and remove their container; `make test-install-ci ARCH=cpu` passes (9 ok).
- [x] 5.25 Publishing: every push run publishes to its repo's GHCR (feature branches too, default for now), only after the post-build test passed; `pull_request` runs never push. The second matrix `engine-published-test` runs on every push run, logs in to GHCR with the run's read token, and also chats with every GPU image (run without GPU devices, CPU fallback). Verified locally: llama.cpp cuda/rocm/vulkan and ollama cuda answer "hi" with no GPU attached.
- [x] 5.24 From CI run 37372371419 (macOS): native engine smoke renders the skill env with the run port (ollama OLLAMA_HOST hung 600 s on the default port), and runs the endpoint pytest with uv and the locked deps instead of the docker test image (no docker on macOS; was `nerdctl: not found`). Prism/LaurentZuijdwijk cuda images run their build-time `--help` check against the toolkit libcuda stub. Verified locally: native + container endpoint checks pass against the llama.cpp cpu image.
- [x] 5.23 `make install-prism-cpu|upstream-cpu|prism-cuda|upstream-cuda` install the engine image (no host build); only the Metal targets build natively. README "Which llama.cpp build is used", the install targets list, `make help`, issue #98 and the PR body describe the container-only install, the two CI test stages and the picker.
- [x] 5.22 Issue #102 in this PR: `engine-published-test` matrix (jobs `test-published-<engine>-<arch>`, every push run, after engine-image) pulls every image from GHCR (`make test-published-engine`: local copy removed, digest == `:<arch>`, binary version, container answers "hi" on `/v1/chat/completions`, GPU images on CPU), then `make engine-launchers` (pull only) + `make test-built-engine`.
- [x] 5.21 Start scripts and the llama-server shim name their container per port and remove it when killed (tests leaked containers).
- [x] 5.20 cuda containers get the HOST driver through the nvidia-container-toolkit CDI device (`--device nvidia.com/gpu=all`) in make run-engine, every start script and the llama-server shim; `--gpus all` failed on Docker 29 ("AMD CDI spec not found"). Install fails loudly on a cuda host without the CDI spec. Verified on an RTX 4090: start script served the 0.5B model on CUDA0 (1052 MiB) and answered "hi". Prism/LaurentZuijdwijk cuda builds link without a driver at build time.
- [x] 5.19 `make uninstall` undoes the container install: launcher, llgenie.py, generated start scripts + llama-server shim (marker-checked), stops `llgenie-*` containers, `PURGE_IMAGES=1` removes engine images; no longer `rm -rf`s source trees. Verified locally and asserted in `make test-install-ci`.
- [x] 5.18 The test image no longer builds its own llama-server (an old ggerganov clone with `-DLLAMA_CUBLAS=OFF`). It carries python/pytest/deps/hf/docker CLI only. `test-install-ci`, `test-health` and `test-top-tier-serve-ci` run in it with the host docker socket mounted and serve through the llama.cpp engine image. Verified locally: `make test-health` answered "hi" through the image.
- [x] 5.17 CI `install` job runs the real `make install` on the runner (docker engine images + start scripts), `make test-built-engine`, the install tests, "hi" through the container llama-server (`make test-health-host`) and `make uninstall` (`make test-install-ci`).
- [x] 5.16 CI builds without pushing, tests, then `make push-engine` on main only (after tests). PRs never push.
- [x] 5.15 `make install` = pull/build every engine image for this host + `~/bin/llgenie-engine-<id>` start scripts + `~/bin/llama-server` container shim, then `make test-built-engine` (every script prints its version through its image). No native engine build.
- [x] 5.14 Post-build pytest stage per engine variant (`tests/test_engine_runs.py`): cpu = serve + "hi" on the OpenAI endpoint; GPU = `version`/`detect` binary check (entrypoint adds a `version` alias). Verified locally.
- [x] 5.13 GPU-image detect = package-metadata version probe (vllm/tensorrt-llm/mlx), not engine init, so it passes on GPU-less CI. vulkan base + libgomp1. ROCm compile path sets CUDA_HOME/ROCM_HOME=/opt/rocm; sglang adds CXXFLAGS=-std=c++20.
- [x] 5.12 The official ggml-org llama.cpp images set `ENV LD_LIBRARY_PATH=/app` (their llama-server rpaths $ORIGIN for libllama-server-impl.so, which llgenie's WORKDIR change breaks). Fix verified locally.
- [x] 5.11 The Linux `server-variants` job is replaced by the engine images: each variant runs from its own base image with a test stage on the OpenAI API (cpu: serve + `/v1/models` + `/v1/chat/completions`; GPU: `make test-engine-image` info + detect). macOS Metal variants stay native. Fixes from CI: env `{host}` is bound at run time (ollama), HF cache dir is created (mlx), Vulkan gets `spirv-headers`, the LaurentZuijdwijk launch drops MTP by default, the freetoken ROCm build gets CUDA_HOME/ROCM_HOME, exllamav3 gets newer packaging/setuptools, and mlx-cuda detect needs no driver at build.
- [x] 5.7 No host venvs: skills install into the image's Python (`--system`), Metal uses `uv tool install`, and native install/serve on image backends is refused with a pointer to `make build-engine`.
- [x] 5.6 CI `engine-matrix` + `engine-image`: the job list comes from the params (`make list-engine-images CI=1 JSON=1`, 29 engine x backend jobs). Each job runs in parallel: `make build-engine`, the post-build test, then `make push-engine` (see 5.25). `engine-smoke-mac` installs Metal engines natively. Builds run only in CI, followed with `make ci-engine-images`.
- [x] 5.8 One generated Dockerfile per engine x backend (`containers/engines/dockerfiles/<id>/Dockerfile.<backend>`, GPU arch as a fat build), plus shared toolchain bases per backend (`containers/engines/base`), published with a buildx registry cache, FROM the official upstream image where one exists (vllm, ollama, sglang, tensorrt-llm), else a devel base with a slim runtime stage (llama.cpp family).
- [x] 5.3 README "Engine skills" section. Issue #98 body is synced with this change.

## Verification

- [x] 6.5 Host (light only): one llama.cpp cpu image was built locally early on. Since then, all images build only in CI (no local servers, no local builds).
- [x] 6.4 Host: `make build-engine ENGINE=llama.cpp ARCH=cpu-portable` built from the frozen params at the pinned sha (8f9ae20c8). The second run printed "exists -> no rebuild". `make run-engine` became READY at `http://127.0.0.1:18441/v1` with `llm-local` and answered "hi". The container HEALTHCHECK passed and the port was bound to 127.0.0.1 only.

- [x] 6.1 Host (RTX 4090 Laptop, cc 8.9, CUDA 13.3): `make build-variant TREE=prism BACKEND=cuda` built through the skill with `-DCMAKE_CUDA_ARCHITECTURES=89` (CMakeCache confirms), and `make test-serve-variant TREE=prism BACKEND=cuda` answered "hi".
- [x] 6.2 Host: `make engine-install ENGINE=ollama` installed v0.35.1 (`sha256sum -c` OK) and served `llm-local` on CUDA (log `library=CUDA compute=8.9`, "hi" answered). vLLM 0.31.0 served `llm-local` on the GPU (Qwen2.5-0.5B, /health OK, "hi" answered). This was an early host install, since superseded: engines now run only from their images.
- [x] 6.3 `make test-unit` (446 passed), `make lint`, `make skills-validate` (fixture and live registry: 16/16, 0 errors) and `make openspec-validate NAME=feat-engine-skills` pass.
