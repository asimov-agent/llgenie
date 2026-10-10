# Tasks

## macOS parity install — same pipeline, per-OS engines, per-engine install in its own environment

- [x] Update the GitHub issue (#120) with the full parity contract: same pipeline on both OSes, per-OS engine sets, `make install` per engine in its own environment.
- [x] Create the OpenSpec change (`macos-parity-install`) with proposal + spec; wire every scenario to its test file.
- [x] Add the bash-5 init gate to the Makefile (`SHELL` = brew's bash on macOS / /bin/bash on Linux; `make bash-check` installs via `brew install bash` when missing and fails closed on bash 3.2).
- [x] Add the spec-driven tests to `tests/test_macos_install.py`: bash 5 present / installed-when-missing / fails-closed-on-3.2, pure-make-surface (make target runs the python script).
- [x] Per-OS per-engine install proof: Linux proves each container engine it supports via `make test-install-published` (per backend, in the test container, engines answer "hi"); macOS proves each native-Metal engine it supports via `make test-native-engine` / `make test-interactive-tensorfold-ci` (native install, Metal serve). Both hard-fail on any skip. Documented in the issue + README.
- [x] Wire the per-engine install proof into CI for Linux container engines via `published.yml`; macOS native Metal engines run `make ci-engines BACKEND=metal` on an Apple-Silicon host (no CI job, see §17).
- [x] Bump the `llgenie/test` image base `python:3.10-slim` -> `python:3.11-slim` (and tools/Dockerfile) and recompile the tools lockfiles.
- [x] Create the gguf venv with Python 3.11 (`scripts/check_python.py`, brew python@3.11 on macOS); the macOS CI job sets up Python 3.11.
- [x] Unify the engine row into ONE make target: `make ci-engines BACKEND=<b>` -> `scripts/ci_engines.py` (Linux: `test-install-published`; macOS: `test-native-engines` + the TensorFold targets); `published.yml` calls it on Linux.
- [x] Add `make test-native-engines` (`tests/test_native_engines.py`): `make install` path for EACH native-Metal engine (litert, mlx, ollama, tensorfold), pinned version, tiny model on Metal + "hi".
- [x] Hermetic tests for ci_engines / check_python / the native matrix in `tests/test_macos_install.py`; spec scenarios name them.
- [x] Push and confirm the CI run for the branch reports the new steps (`make ci-engines`) per OS.
- [x] Update README.md to document the parity contract: same pipeline, per-OS engine sets, every make command runs its Python script, bash-5 init gate.
- [x] Run `make lint-fix` (trailing newlines), `make test-unit`, and `make openspec-validate NAME=macos-parity-install` — all must be green.
- [x] On this macOS host, verify the bash-5 gate and the pure-make-surface tests pass with real `make` output.

## 4. macOS parity follow-up (issue #120, CI run 37890648373)

- [x] 4.1 Run macOS on the SAME `pipeline.yml` as Linux (one job per `make ci-<job>`, no combined jobs); delete `pipeline-macos.yml`.
- [x] 4.2 Install bash 5 at make-parse time (`check_bash.py --resolve`) so a fresh macOS runner needs no second `make` (bash-check exit 3 failed every macOS job).
- [x] 4.3 Retry README link checks on 5xx / network errors (GitHub 504s failed `linux / unit`).
- [x] 4.4 Native-Metal matrix = `model_engine_pick.metal_engines()`: llama.cpp and llama.cpp-prism are built natively with Metal and serve the tiny GGUF + "hi".
- [x] 4.5 Superseded by §17: there is no `native-engine-macos-arm64` CI job.
- [x] 4.6 Hermetic tests lock the shared pipeline file, the gating end-of-pipeline native job, the native matrix (incl. llama.cpp + prism), bash resolve and the link retry; the CI-green proof is tracked on issue #120.
- [x] 4.7 macOS runs every make test stage in the Python 3.11 venv (`TEST_RUN`/`engine_test` Darwin branch, `make test-env`), no test container; CI jobs call `make test-env`.

## 5. macOS CI never runs a Docker GitHub Action (issue #120, run 37901591214)

- [x] 5.1 The Docker action's macOS step is a no-op, and install / cpu-health / top-tier / openspec / install-published call it only on Linux (`runner.os == 'Linux'`); install-published is Linux only (§17).
- [x] 5.2 `ci-install`, `ci-cpu-health` and `ci-top-tier` run the same targets on both OSes. The early macOS install is not a second native-engine install; native-Metal engines stay `make ci-engines BACKEND=metal`.
- [x] 5.3 `tests/test_macos_install.py::test_macos_ci_does_not_run_docker_github_actions` locks both, and the README no longer says the macOS runner runs Docker.
- [x] 5.4 Every macOS job and every Linux job is required (`continue-on-error: false`, no `optional: true`): a failure on either OS fails the run.

## 6. Verify

- [x] 6.1 `make openspec-validate NAME=macos-parity-install` exits 0 on the pinned CLI (1.10.0). `make test-unit` is the linux/macos unit jobs on this push.

## 7. install waits for the image this same run is publishing (issue #120, runs 37912917299 / 37915550379)

- [x] 7.1 `pull_published` retries a missing tag (the engine-image job can still be pushing) and still fails with `not published` after the retries.
- [x] 7.2 `tests/test_macos_install.py::test_pull_published_retries_a_tag_the_parallel_job_has_not_pushed_yet` locks it.

## 8. the runner uses the bash make selected (issue #120, run 37929800971)

- [x] 8.3 The serve fixture is `scripts/loopback_server.py` (binds and listens with no `socket.getfqdn()`), not `python3 -m http.server`. On the macOS 15 runner that lookup stalls ~35s between bind and listen (actions/runner-images#14409), so the 30s probe reported the server dead while it was still alive. `tests/test_macos_install.py::test_loopback_fixture_does_no_hostname_lookup`.
- [x] 8.1 `engine_runner` and `engine_smoke` run their `bash -c` under `LLGENIE_BASH` (the Makefile's bash 5), never bare `bash` — on the macOS runner that is `/bin/bash` 3.2, a login shell that drops the 3.11 venv, so `python3 -m http.server` never binds.
- [x] 8.2 `tests/test_macos_install.py::test_runner_serves_with_the_bash_make_selected_not_bin_bash` locks it; the spec scenario names the test.

## 9. a native version check does not need the engine's daemon (issue #120, run 37940784909)

- [x] 9.1 `engine_skills._detect_run` treats a printed version as installed even when the detect command exits non-zero because its daemon is down (`ollama --version` on a fresh macOS install). A non-zero exit with no version line is still missing.
- [x] 9.2 `tests/test_engine_skills.py::test_detect_accepts_a_version_when_the_daemon_is_down` locks it; `make test-unit` (799 passed) and `make openspec-validate NAME=macos-parity-install` are green.

## 10. the install job pulls the published images (issue #120, run 37957085562)

- [x] 10.1 `make test-install-ci` runs `make install` without `BUILD=1`, on both OSes. Building the engine images inside that job on the 7 GB macos-15-intel runner starved it until GitHub killed the job. The published install job already proves the pull per backend.
- [x] 10.2 `tests/test_engine_skills.py::test_pre_publish_jobs_build_and_the_pull_only_install_runs_last` locks it; `make test-unit` and `make openspec-validate NAME=macos-parity-install` are green.

## 11. a published port is reached from inside the test container, and a small Mac names TensorFold's budget (issue #120)

- [x] 11.1 `tests/test_install_published.py` probes the published engine on the host the test process can reach (`host.lima.internal` / `host.docker.internal` from inside the test container, loopback on the host). `127.0.0.1` inside the container is the container, so a Mac published port was never answered.
- [x] 11.2 `tests/test_native_engine_light.py` asserts TensorFold's own budget line (`need more than`) and the start script's `do not fit`, not a phrase TensorFold does not print.
- [x] 12.1 `make ci-install` prepares the environment (`make test-env`), then runs `make install`, `$HOME/bin/llgenie --dry` and `make uninstall` as separate make targets. macOS never runs those in a container, and the install job does not start Colima. Linux runs `make install`, the dry run and `make uninstall` inside the test container (the dry run uses the home `make install` wrote). The pipeline install job calls `make ci-install` on both OSes.
- [x] 12.2 The lock tests pass. `make test-unit` and `make openspec-validate NAME=macos-parity-install` are green.
- [x] 13.1 macOS `make install` (no `--arch`) does not start Colima and does not pull an engine image when the container runtime is down. `make test-uninstalled` does not call the runtime on Darwin. Linux still pulls images.
- [x] 13.2 No macOS CI job starts Colima. pipeline.yml gates the Docker action with `runner.os == 'Linux'`; published.yml is Linux only. The Docker action fails if a macOS job calls it. The README says macOS CI never starts Colima.

## 14. macOS never starts an engine image (issue #120)

- [x] 14.1 On macOS, `llgenie` and `make install` never start or pull an engine image. Apple Silicon offers only native Metal engines; a container-only engine is not offered and is not pulled. Linux still pulls this host's images, including the cpu fallback.
- [x] 14.2 `tests/test_macos_install.py` and `tests/test_mac_trend_pick.py` lock it. `make ci-unit` and `make openspec-validate NAME=macos-parity-install` are green.

## 15. macOS install has uv before make install (issue #120, run 37998420484)

- [x] 15.1 `make test-env` on Darwin installs `uv` with Homebrew when it is not on PATH, then checks it is there. `make install` still fails loudly if `uv` is missing. Linux `test-env` is unchanged.
- [x] 15.2 `tests/test_macos_install.py::test_macos_test_env_installs_uv_before_make_install` locks it. `make openspec-validate NAME=macos-parity-install` is green.

## 16. Intel macOS does not install arm64 Metal engines (issue #120, run 38001242985)

- [x] 16.1 `make install` on Darwin `x86_64` installs no Metal engine and pulls no image. LiteRT, MLX and TensorFold publish arm64 wheels; the macos-15-intel job cannot install them. Apple Silicon still installs every Metal engine. Linux is unchanged.
- [x] 16.2 `tests/test_macos_install.py::test_intel_mac_install_does_not_install_metal_engines` locks it. `make openspec-validate NAME=macos-parity-install` is green.
- [x] 16.3 Because Intel macOS `make install` writes nothing, the `test-built-engine` and `uninstall` steps that follow it are a no-op that exits 0 there (nothing to version-test, nothing to remove); Linux still fails loudly when no start scripts were written.
- [x] 16.4 `tests/test_macos_install.py::test_intel_mac_built_engine_test_and_uninstall_are_noops` locks it; the lock tests and `make openspec-validate NAME=macos-parity-install` are green.
- [x] 16.5 An explicit `--ensure <engine> --arch metal` still reaches the native install on Intel macOS (the llgenie pick path, driven hermetically by `LLAMA_BACKEND=metal`); an explicit non-metal `--arch` is refused. `tests/test_macos_install.py::test_intel_mac_ensure_still_installs_a_metal_engine_natively` locks it.

## 17. No macOS published-image stage and no native-engine CI job (issue #120, run 38012660601)

- [x] 17.1 `ci.yml` drops `macos-published` (it failed with `docker: command not found`: macOS never runs an engine container, so it has no published images to test) and `native-engine-macos-arm64` (GitHub's macOS runners have no Metal GPU; the job never finished). `published.yml` is Linux only. Native-Metal engines stay `make ci-engines BACKEND=metal` on an Apple-Silicon host.
- [x] 17.2 `tests/test_macos_install.py::test_macos_has_no_published_image_or_native_engine_ci_job` locks it; README, AGENTS.md and the spec say the same. `make test-unit`, `make lint` and `make openspec-validate NAME=macos-parity-install` are green.
