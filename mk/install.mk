# Host-install domain (issue #800, split #2461): `make install` -> launcher + symlinks +
# engine containers + host tests. Everything here lived in the top Makefile before the split;
# recipes are byte-identical (the split only relocates them).

all: bash-check install

# ---- full install: engine images + venv + launcher + start scripts ---------
# `make install` does NOT build a native llama-server anymore. Entry points run
# through the engine CONTAINER images (issue #98): it
#   1. builds the gguf-tooling venv (venv-install, for llgenie_serve.py metadata/tuning)
#   2. builds every engine image (llama.cpp, prism, ...) via `make build-engines` on
#      the detected DEFAULT arch, or pulls the published image,
#   3. writes a start script per engine image into ~/bin (engine-launchers) —
#      scripts that docker-run the image with the model mounted,
#   4. verifies each shim: `docker run … version` must report the engine version
#      (test-launchers; the Metal engine, which can not run headless, is skipped).
# llgenie.py resolves `llama-server` to the container shim below.

# ---- full install: engine images + venv + launcher + start scripts ---------
# `make install` does NOT build a native llama-server anymore. Entry points run
# through the engine CONTAINER images (issue #98): it
#   1. builds the gguf-tooling venv (venv-install, for llgenie_serve.py metadata/tuning)
#   2. builds every engine image (llama.cpp, prism, ...) via `make build-engines` on
#      the detected DEFAULT arch, or pulls the published image,
#   3. writes a start script per engine image into ~/bin (engine-launchers) —
#      scripts that docker-run the image with the model mounted,
#   4. verifies each shim: `docker run … version` must report the engine version
#      (test-launchers; the Metal engine, which can not run headless, is skipped).
# llgenie.py resolves `llama-server` to the container shim below.
install: bash-check venv-install engine-launchers link test-built-engine smoke provision-agent-profiles
	@echo
	@echo "Installed (published engine images for this host's backend pulled + start scripts written + version-tested)."
	@echo "Run '$(LAUNCHER)' (e.g. 'llgenie --list', 'llgenie qwen'), or e.g. '$(BIN)/llgenie-engine-llama-cpp ~/models/m.gguf'."
	@echo "Tips: 'make run-engine ENGINE=<id> MODEL=<m>' / 'make stop-engine ...' run/stop an engine image."

# ---- 1. build the gguf-tooling venv (Python 3.11 + gguf + numpy) --------

# ---- 1. build the gguf-tooling venv (Python 3.11 + gguf + numpy) --------
venv-install:
	@echo "==> Building gguf venv at $(VENV)"
	$(MAKE) -C tools venv-install

# ---- 2+3. launcher wrapper + symlink into ~/bin -------------------------

# ---- 2+3. launcher wrapper + symlink into ~/bin -------------------------
link:
	@mkdir -p "$(BIN)"
	@printf '#!/usr/bin/env bash\n# llgenie launcher -> runs %s with the %s venv.\n# Prepend ~/bin to PATH so the llama-server symlink there resolves in any shell.\nexport PATH="$(BIN):$$PATH"\nexec "%s" "%s" "$$@"\n' \
		"$(REPO)/scripts/llgenie_serve.py" "$(VENV)" "$(PY)" "$(REPO)/scripts/llgenie_serve.py" > "$(LAUNCHER)"
	@chmod +x "$(LAUNCHER)"
	@ln -sfn "$(REPO)/scripts/llgenie_serve.py" "$(BIN)/llgenie.py"
	# ~/bin/llama-server is the container shim written by engine-launchers (no native build).
	@echo "==> Wrote $(LAUNCHER) (exec) and symlinked ~/bin/llgenie.py -> repo"
	@$(PY) scripts/ensure_user_path.py

# ---- 4. smoke: confirm the launcher can list models ---------------------

# ---- 4. smoke: confirm the launcher can list models ---------------------
smoke:
	@echo "==> Smoke test: $(LAUNCHER) --list"
	- if $(LAUNCHER) --list; then echo "==> OK: launcher runs and found models."; else echo "==> Launcher installed and runs. (No .gguf under ~/models yet — install succeeds; use 'llgenie --download-top-tier' to fetch trending top-tier models, or drop a .gguf into ~/models and run 'make list'.)"; fi

# ---- llama.cpp server clone-or-pull + build (the right tree/backend) ------
# Auto-detects the tree from card RAM (Prism <= 24 GB, upstream > 24 GB) and the
# backend from the hardware (Metal / CUDA / CPU) via scripts/detect_server.py,
# then runs scripts/build_llama_server.sh to clone-or-pull the tree to the
# LATEST commit and build it. Writes the built binary path to SERVER_BIN_STAMP
# so `link` symlinks it into ~/bin.
#
# On the host this builds ONLY the right variant for the card (e.g. prism+cuda
# on a 16 GB NVIDIA card). In CI, the build-variants job (ci.yml) calls
# `build-variant` for each tree x backend combo instead.

# ---- helpers ------------------------------------------------------------
list:
	@$(LAUNCHER) --list


generate-requirements: ## Recompile tools/requirements.in -> tools/requirements.txt (container or venv pip-compile)
	$(MAKE) -C tools generate-requirements


test-install: ## Host install tests (containerized) — skips cleanly without artifacts
	$(TEST_RUN) python -m pytest tests/test_install.py -p no:cacheprovider -q

# Native (non-container) engine tests are hardware-scoped (issue #114): only Metal runs
# natively, so they have test cases only on an Apple-Silicon Mac. On any other host
# (every Linux CI job, cuda/rocm/vulkan/cpu) these targets have no case for that
# hardware and say so; the Linux engines are tested through their images instead.
# NATIVE_HOST= simulates a non-Metal host.
NATIVE_HOST ?= $(shell [ "$$(uname -s)-$$(uname -m)" = "Darwin-arm64" ] && echo metal)
NATIVE_GUARD = [ "$(NATIVE_HOST)" = "metal" ] || { echo "[$@] native engines are Metal-only: this host ($$(uname -s) $$(uname -m)) has none; its engines are tested in their images (make test-engine)"; exit 0; };


NATIVE_HOST ?= $(shell [ "$$(uname -s)-$$(uname -m)" = "Darwin-arm64" ] && echo metal)
NATIVE_GUARD = [ "$(NATIVE_HOST)" = "metal" ] || { echo "[$@] native engines are Metal-only: this host ($$(uname -s) $$(uname -m)) has none; its engines are tested in their images (make test-engine)"; exit 0; };

test-native-engine: ## Apple-Silicon host: REAL native TensorFold install/update/reuse through the llgenie pick (real uv, isolated tool dir)
	# issue #114: a Metal engine runs natively (Metal cannot run in a container), so
	# this runs on the macOS arm64 host with the gguf venv python, never in the test image.
	@$(NATIVE_GUARD) env -u PYTHONPATH $(PY) -m pytest tests/test_native_engine_real.py -p no:cacheprovider -q -s


test-native-engines: ## Apple-Silicon host: make install for EACH native-Metal engine (litert, mlx, ollama, tensorfold) in its own environment: skill install at the pin, start script version, tiny model served on Metal + "hi" (issue #120)
	@$(NATIVE_GUARD) env -u PYTHONPATH $(PY) -m pytest tests/test_native_engines.py -p no:cacheprovider -q -s


test-native-engine-serve: ## Apple-Silicon host: + `llgenie --select 1 --engine tensorfold` downloads, installs and serves on Metal, answers "hi"
	@$(NATIVE_GUARD) env -u PYTHONPATH LLGENIE_NATIVE_SERVE=1 $(PY) -m pytest tests/test_native_engine_real.py -p no:cacheprovider -q -s


test-native-engine-light: ## Apple-Silicon host: the lightest TensorFold model (Qwen3.5-9B MLX 4-bit) via the llgenie start script: serves on Metal + "hi" when TensorFold's plan fits this host, else the budget refusal (7 GB CI runner)
	@$(NATIVE_GUARD) env -u PYTHONPATH $(PY) -m pytest tests/test_native_engine_light.py -p no:cacheprovider -q -s


test-interactive-tensorfold: ## Apple-Silicon host: plain interactive `llgenie`, pick Qwen3.8-27B then TensorFold from the printed lists, installs TensorFold, serves on Metal, "hi"
	# TEST_LAUNCHER=~/bin/llgenie tests the installed launcher (after make install); default: the repo script
	@$(NATIVE_GUARD) env -u PYTHONPATH $(if $(TEST_LAUNCHER),LLGENIE_LAUNCHER=$(TEST_LAUNCHER)) $(PY) -m pytest tests/test_interactive_tensorfold_real.py -p no:cacheprovider -q -s


test-interactive-tensorfold-ci: ## macOS arm64 CI runner: the same two interactive picks (48 GB Mac emulated, --dry) + the REAL TensorFold install; no Metal serve (7 GB runner)
	@$(NATIVE_GUARD) env -u PYTHONPATH LLGENIE_NO_SERVE=1 $(PY) -m pytest tests/test_interactive_tensorfold_real.py -p no:cacheprovider -q -s


test-install-host: ## Verify the REAL host install (make install) — runs on the host where ~/bin/llgenie + ~/models exist
	# Runs tests/test_install.py with the gguf venv python on the HOST, so the
	# actual `make install` artifacts (~/bin/llgenie launcher, symlinks,
	# ~/bin/llama-server, ~/models) are asserted — not skipped. This is the
	# local/AGENTS.md proof that `make install` works.
	@echo "==> Verifying host install artifacts via tests/test_install.py"
	@$(PY) -m pytest tests/test_install.py -p no:cacheprovider -q


test-install-ci: ## LOCAL, one container: REAL make install (engine images via the host docker socket) -> test-built-engine -> install tests -> "hi" through the container llama-server -> trend pick -> uninstall (NO SKIP). CI covers the same flow as separate stages through `make ci-install`; no job runs THIS target (issue #239)
	# Python, pytest and the hf/docker CLIs come from the test image; every
	# inference server runs in its engine image (started through the host docker
	# socket). HOME is a throwaway dir inside the repo (.ci-home).
	@echo "==> test-install-ci (test container + engine images)"
	@mkdir -p "$(CI_HOME)"
	$(ENGINE_TEST_RUN) sh -c 'make install ARCH=$(if $(ARCH),$(ARCH),cpu) && make -C tools venv-dev-install && HF_BIN=$$(command -v hf) python3 scripts/download_test_model.py && make test-install-host && make test-health-host && make test-install-trend && touch ~/bin/not-ours && make uninstall && make test-uninstalled && test -e ~/bin/not-ours && echo "==> uninstall removed every installed file, kept foreign files, no engine container left"'
	@$(CI_HOME_CLEAN)


test-uninstalled: ## After make uninstall: no installed launcher, shim or llgenie-engine-* is left in ~/bin, no llgenie engine container runs, the repo is untouched
	@test ! -e "$(LAUNCHER)" && test ! -e "$(BIN)/llgenie.py" && test ! -e "$(BIN)/llama-server" && test ! -e "$(BIN)/prism-server" \
	  || { echo "FAIL: make uninstall left a launcher or shim in $(BIN)"; exit 1; }
	@! ls "$(BIN)"/llgenie-engine-* >/dev/null 2>&1 || { echo "FAIL: make uninstall left llgenie-engine-* in $(BIN)"; exit 1; }
	@if [ "$(HOST_OS)" = Darwin ]; then echo "==> uninstall removed every installed file (macOS: no container runtime was started)"; exit 0; fi
	@test -z "$$($(RUNTIME) ps -q --filter name=^llgenie-)" || { echo "FAIL: an llgenie engine container is still running"; exit 1; }
	@test -f scripts/llgenie_serve.py || { echo "FAIL: repo touched"; exit 1; }
	@echo "==> uninstall removed every installed file, no engine container left"


test-health-host: ## After make install: llgenie serves the 0.5B model through ~/bin/llama-server (the llama.cpp image) and answers "hi"
	@HF_BIN="$${HF_BIN:-$$(command -v hf)}" $(PY) scripts/download_test_model.py
	$(PY) -m pytest tests/test_health.py -p no:cacheprovider -q -s


test-recall-step: ## Host proof of the orchestrator STEP 2 recall fallback (issue #2186): asserts the pinned 9177 recall returns `results` and that the wrong default port 8888 fails while 9177/health succeeds. Needs the live hindsight daemon on 127.0.0.1:9177 (HINDSIGHT_API_PORT in ~/.hindsight/profiles/hermes.env), which no CI runner has, so it is kept OUT of the hermetic gate (tests/fixtures/unit-suite.json) and run on the tick host
	@$(PY) -m pytest tests/test_procedure_recall_step.py -p no:cacheprovider -q


test-install-trend: ## After make install: ~/bin/llgenie with no model in a pty -> recommended list from data/models.json -> pick 1/1 -> real GGUF download -> engine container answers "hi" (issue #105)
	$(PY) -m pytest tests/test_install_trend.py -p no:cacheprovider -q -s


test-install-published: ## After CI published the images: in the test container, make install for BACKEND (mocked via LLAMA_BACKEND; GPU images on CPU) pulls ONLY that backend's published images, llgenie answers "hi" through llama-server and prism-server, --pick --engine pulls the picked engine on first use, the installed llgenie with no model (pty) picks the top trend model + engine, downloads the full GGUF and answers "hi" (issue #105), make uninstall leaves nothing
	@test -n "$(BACKEND)" || { echo "Usage: make test-install-published BACKEND=cpu|cuda|rocm|vulkan"; exit 1; }
	@mkdir -p "$(CI_HOME)"
	$(call engine_test,LLAMA_BACKEND=$(BACKEND) LLGENIE_NO_GPU=1) sh -c 'HF_BIN=$$(command -v hf) python3 scripts/download_test_model.py && python3 -m pytest tests/test_install_published.py -p no:cacheprovider -q -s'
	@$(CI_HOME_CLEAN)


download-test-model: ## Fetch the lightweight (0.5B Q4 ~340MB) model into container ~/models/Qwen/8GB
	$(TEST_RUN) python scripts/download_test_model.py


loop: loop-harness ## alias

loop-harness: bash-check ## Loop runner (host orchestration): image->download->lint->unit->install->health->test->openspec
	# The harness orchestrates the other stages by shelling out to `make`, so it
	# MUST run on the host (where make + nerdctl/docker live), NOT inside the
	# test container. It only needs python stdlib.
	@python3 scripts/loop_harness.py

# Run every verification step explicitly (Makefile-level chain, same order as
# loop-harness). Fails fast on the first failing step.

# Run every verification step explicitly (Makefile-level chain, same order as
# loop-harness). Fails fast on the first failing step.
chained: bash-check test-unit test-agents-read test-install test-health test openspec-validate
	@echo "All chain steps completed."


uninstall: ## Undo make install: ~/bin/llgenie, llgenie.py, the llgenie-engine-* start scripts + llama-server shim; stop engine containers (PURGE_IMAGES=1 also removes the engine images). Keeps venv, models, repo, source trees.
	# Removes only what `make install` wrote (start scripts carry a
	# "Generated by `make install`" marker; a symlinked ~/bin/llama-server from the
	# old native install is removed too). It never deletes repo source, models,
	# or any git checkout under ~/repository/git: install no longer clones or
	# builds llama.cpp on the host, so uninstall has no tree to remove.
	@rm -f "$(LAUNCHER)" "$(BIN)/llgenie.py"
	@python3 scripts/install_engine_launchers.py --bin "$(BIN)" --uninstall $(if $(PURGE_IMAGES),--purge-images,)
	@rm -f "$(SERVER_BIN_STAMP)"
	@echo "Removed $(LAUNCHER) and $(BIN)/llgenie.py (venv kept at $(VENV); models and repo untouched)"

# ---- ci-<job>: ONE make target per CI pipeline job (issue #117) -------------
# pipeline.yml runs each as one job, on Linux AND on macOS (issue #120: the same
# file, no combined jobs). The commands are the same on both OSes. Every target
# that runs in a container needs the pulled llgenie/test (or llgenie/openspec) image:
# CI pulls the test image first with `make test-image-pull`; the openspec gate pulls-or-builds
# with `make openspec-image` (a fork PR cannot publish a NEW hash, issue #1673).

