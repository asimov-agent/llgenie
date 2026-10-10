# llgenie install Makefile.
#
# `make install` does the WHOLE setup so you never touch the venv manually:
#   1. builds the Python 3.11 gguf-tooling venv (./tools/venv-install)
#   2. writes a runnable launcher `~/bin/llgenie` that executes `llgenie.py`
#      with the venv's python (so `gguf`/`numpy` resolve without extra steps)
#   3. symlinks `~/bin/llgenie.py` -> this repo's `llgenie.py`
#   4. verifies the install with a `--list` smoke run
#
# After `make install` you can simply run:
#       llgenie                 # interactive picker
#       llgenie --list          # list models
#       llgenie qwen            # launch by substring
#       llgenie --dry qwen      # print the tuned command, don't run

# Use a bash 5 recipe shell on BOTH OSes. On macOS the system bash is 3.2, so the
# shell is brew's bash 5; Linux/CI runners already have bash 5 in /bin/bash.
# scripts/check_bash.py --resolve picks it at make-parse time and, on macOS, first
# `brew install`s bash when it is missing, so the SAME make run already uses bash 5
# (a fresh runner needs no re-run). The `bash-check` gate (prerequisite of install /
# ci-* / loop) then fails closed if the recipe shell is still not bash 5.
SHELL    := $(shell python3 scripts/check_bash.py --resolve || command -v bash || echo /bin/bash)
export LLGENIE_BASH := $(SHELL)
HOME    := $(shell printf '%s' "$$HOME")
BIN     := $(HOME)/bin

# ---- bash 5 recipe-shell gate (parity: macOS uses brew bash 5, Linux bash 5) --
# The actual SHELL was already resolved to brew's bash at make-parse time (see
# the SHELL assignment above); this target is a thin entrypoint that runs
# scripts/check_bash.py — the single source of truth for the bash-5 parity check.
# On macOS it installs bash via `brew install bash` when missing; it fails closed
# if the recipe shell is not bash 5 (so no stage ever runs under bash 3.2).
bash-check:
	@python3 scripts/check_bash.py "$(SHELL)" $(if $(CHECK_BASH_FORCE),--force,)

# Put ~/bin on PATH for every recipe so `llama-server` (symlinked there by
# `make install`) resolves even in non-interactive make subprocesses — not just
# in an interactive zsh that sourced ~/.zshrc.
export PATH := $(BIN):$(PATH)
REPO    := $(shell pwd)
VENV    := $(HOME)/llama-gguf-tools/.venv
# Prefer the venv python (host install) but fall back to a plain `python3`
# when the venv is absent — e.g. a bare GitHub Actions runner. This lets the
# same Makefile test/lint targets run identically on the host and in CI.
PY      := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
LAUNCHER := $(BIN)/llgenie
# Where llama.cpp trees get cloned (clone-or-pull + build). On the host this is
# the user's git home; in CI the variant jobs set SERVER_ROOT to a local dir.
SERVER_ROOT ?= $(HOME)/repository/git
# Stamp file holding the path of the freshly-built llama-server binary (written
# by `build-server`). `link` symlinks ~/bin/llama-server from it, so build and
# link always agree on the binary.
SERVER_BIN_STAMP := $(HOME)/.llgenie/server.bin.path

.PHONY: all install venv-install link uninstall smoke list version help test-native-engine test-native-engine-serve test-interactive-tensorfold test-interactive-tensorfold-ci \
	openspec-image openspec-new openspec-validate openspec-status openspec-shell \
	test test-unit test-agents-e2e test-agents-read agents-read-venv test-install test-install-ci test-install-host test-install-trend test-health test-health-host download-test-model \
	test-image test-image-pull openspec-image-pull publish-ci-images ci-image-refs test-clean lint lint-fix loop loop-harness chained cron-install cron-uninstall cron-snapshot \
	build-server build-variant serve-variant test-serve-variant stop-serve-variant install-prism-cpu install-upstream-cpu \
	install-prism-cuda install-upstream-cuda install-prism-metal install-upstream-metal \
	sync-registry check-registry skills-validate engine-list engine-hardware engine-plan engine-check engine-install engine-detect engine-smoke test-engine ci-engine-images build-engine-base build-engines generate-build-engine-params test-engine-image push-engine test-published-engine test-install-published engine-launchers test-built-engine test-uninstalled \
	sync-quant-catalog check-quant-catalog sync-strata-models check-strata-models \
	generate-engine-params check-engine-params build-engine run-engine stop-engine list-engine-images \
	ci-lint ci-unit ci-cron ci-watch-report ci-dispatch-e2e ci-agents-read ci-openspec ci-cpu-health ci-top-tier ci-install ci-free-disk test-engine-stage

# ---- container runtime: docker -------------------------------------------
RUNTIME ?= docker
OS_IMG := llgenie/openspec:latest

all: bash-check install

# ---- full install: engine images + venv + launcher + start scripts ---------
# `make install` does NOT build a native llama-server anymore. Entry points run
# through the engine CONTAINER images (issue #98): it
#   1. builds the gguf-tooling venv (venv-install, for llama_serve.py metadata/tuning)
#   2. builds every engine image (llama.cpp, prism, ...) via `make build-engines` on
#      the detected DEFAULT arch, or pulls the published image,
#   3. writes a start script per engine image into ~/bin (engine-launchers) —
#      scripts that docker-run the image with the model mounted,
#   4. verifies each shim: `docker run … version` must report the engine version
#      (test-launchers; the Metal engine, which can not run headless, is skipped).
# llgenie.py resolves `llama-server` to the container shim below.
install: bash-check venv-install engine-launchers link test-built-engine smoke
	@echo
	@echo "Installed (published engine images for this host's backend pulled + start scripts written + version-tested)."
	@echo "Run '$(LAUNCHER)' (e.g. 'llgenie --list', 'llgenie qwen'), or e.g. '$(BIN)/llgenie-engine-llama-cpp ~/models/m.gguf'."
	@echo "Tips: 'make run-engine ENGINE=<id> MODEL=<m>' / 'make stop-engine ...' run/stop an engine image."

# ---- 1. build the gguf-tooling venv (Python 3.11 + gguf + numpy) --------
venv-install:
	@echo "==> Building gguf venv at $(VENV)"
	$(MAKE) -C tools venv-install

# ---- 2+3. launcher wrapper + symlink into ~/bin -------------------------
link:
	@mkdir -p "$(BIN)"
	@printf '#!/usr/bin/env bash\n# llgenie launcher -> runs %s with the %s venv.\n# Prepend ~/bin to PATH so the llama-server symlink there resolves in any shell.\nexport PATH="$(BIN):$$PATH"\nexec "%s" "%s" "$$@"\n' \
		"$(REPO)/scripts/llama_serve.py" "$(VENV)" "$(PY)" "$(REPO)/scripts/llama_serve.py" > "$(LAUNCHER)"
	@chmod +x "$(LAUNCHER)"
	@ln -sfn "$(REPO)/scripts/llama_serve.py" "$(BIN)/llgenie.py"
	# ~/bin/llama-server is the container shim written by engine-launchers (no native build).
	@echo "==> Wrote $(LAUNCHER) (exec) and symlinked ~/bin/llgenie.py -> repo"
	@$(PY) scripts/ensure_user_path.py

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
build-server:
	@echo "==> detect_server: tree/backend for this card"
	@python3 scripts/detect_server.py
	@TREE=$(shell python3 -c "import scripts.detect_server as ds; print(ds.detect_all()['tree'])"); \
	BACKEND=$(shell python3 -c "import scripts.detect_server as ds; print(ds.detect_all()['backend'])"); \
	if [ -z "$$TREE" ] || [ -z "$$BACKEND" ]; then echo "ERROR: detect_server produced no tree/backend"; exit 1; fi; \
	echo "==> building server: tree=$$TREE backend=$$BACKEND (clone-or-pull + build)"; \
	set -o pipefail; \
	if command -v stdbuf >/dev/null 2>&1; then LINEBUF="stdbuf -oL -eL"; else LINEBUF=; fi; \
	SERVER_ROOT=$(SERVER_ROOT) $$LINEBUF $(REPO)/scripts/build_llama_server.sh "$$TREE" "$$BACKEND" 2>&1 | tee /tmp/llgenie_srv_build.log; \
	SRV=$$(tail -n1 /tmp/llgenie_srv_build.log); \
	test -x "$$SRV" || { echo "ERROR: build-server did not produce a binary ($$SRV)"; exit 1; }; \
	mkdir -p $(dir $(SERVER_BIN_STAMP)); \
	printf '%s\n' "$$SRV" > $(SERVER_BIN_STAMP); \
	rm -f /tmp/llgenie_srv_build.log; \
	echo "==> server binary: $$SRV (stamped to $(SERVER_BIN_STAMP))"
# Explicit variant build (used by CI build-variants and by make install-<tree>-<backend>).
# Sets the env seams (LLAMA_SERVER_TREE / LLAMA_BACKEND / LLAMA_RAM_BYTES) and runs
# the SAME build_llama_server.sh, then stamps the binary path so `link` can
# symlink it. The tree override (LLAMA_SERVER_TREE) is authoritative, so CI can
# verify each tree+backend independently of the runner's card.
#   make build-variant TREE=prism BACKEND=cuda
# The build log is streamed (tee). Do not send it through `tail` or
# `2>/dev/null`: those hide the CUDA/Metal compile until the job ends.
build-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make build-variant TREE=prism BACKEND=cuda"; exit 1; }
	set -o pipefail; \
	if command -v stdbuf >/dev/null 2>&1; then LINEBUF="stdbuf -oL -eL"; else LINEBUF=; fi; \
	TREE=$(TREE) BACKEND=$(BACKEND) \
		LLAMA_SERVER_TREE=$(TREE) LLAMA_BACKEND=$(BACKEND) \
		LLAMA_RAM_BYTES=17179869184 \
		SERVER_ROOT=$(SERVER_ROOT) $$LINEBUF $(REPO)/scripts/build_llama_server.sh "$(TREE)" "$(BACKEND)" 2>&1 | tee /tmp/llgenie_srv_build.log
	@mkdir -p $(dir $(SERVER_BIN_STAMP))
	@SRV=$$(tail -n1 /tmp/llgenie_srv_build.log); \
		test -x "$$SRV" || { echo "ERROR: build-variant did not produce a binary ($$SRV)"; exit 1; }; \
		printf '%s\n' "$$SRV" > $(SERVER_BIN_STAMP); \
		rm -f /tmp/llgenie_srv_build.log
	@echo "==> stamped server binary: $$(cat $(SERVER_BIN_STAMP))"

# Serve an already-built variant on its own port. Does not rebuild, does not
# relink ~/bin/llama-server, and does not stop whatever is already listening
# (the long-running server keeps its port). PORT empty picks a free
# 127.0.0.1 port. --n-gpu-layers is not passed. llama-server keeps its
# default and takes GPU or CPU, whichever it can.
#   make serve-variant TREE=prism BACKEND=cuda
#   make serve-variant TREE=prism BACKEND=cuda PORT=18080 MODEL=/path/to/model.gguf
serve-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make serve-variant TREE=prism BACKEND=cuda [PORT=] [MODEL=]"; exit 1; }
	$(PY) scripts/serve_variant.py --tree "$(TREE)" --backend "$(BACKEND)" \
		--port "$(if $(PORT),$(PORT),0)" \
		$(if $(MODEL),--model "$(MODEL)",) \
		--server-root "$(SERVER_ROOT)"

# POST "hi" to the variant server, then stop only that process.
#   make test-serve-variant TREE=prism BACKEND=cuda
test-serve-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make test-serve-variant TREE=prism BACKEND=cuda [PORT=] [MODEL=]"; exit 1; }
	$(PY) scripts/serve_variant.py --tree "$(TREE)" --backend "$(BACKEND)" --test \
		--port "$(if $(PORT),$(PORT),0)" \
		$(if $(MODEL),--model "$(MODEL)",) \
		--server-root "$(SERVER_ROOT)"

# Stop the variant server this Makefile started. Does not touch any other port.
#   make stop-serve-variant TREE=prism BACKEND=cuda
stop-serve-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make stop-serve-variant TREE=prism BACKEND=cuda"; exit 1; }
	$(PY) scripts/serve_variant.py --tree "$(TREE)" --backend "$(BACKEND)" --stop

# ---- explicit variant install targets --------------------------------------
# One tree+backend. cpu/cuda run from the engine image (no host build); Metal is
# Apple-only and cannot run in a container, so it is the only native build.
install-prism-cpu: ## Install the Prism llama.cpp engine image (CPU) + start scripts + version test
	$(MAKE) install ENGINES=llama.cpp-prism ARCH=cpu
install-upstream-cpu: ## Install the upstream llama.cpp engine image (CPU)
	$(MAKE) install ENGINES=llama.cpp ARCH=cpu
install-prism-cuda: ## Install the Prism llama.cpp engine image (CUDA; host driver via nvidia-container-toolkit CDI)
	$(MAKE) install ENGINES=llama.cpp-prism ARCH=cuda
install-upstream-cuda: ## Install the upstream llama.cpp engine image (CUDA)
	$(MAKE) install ENGINES=llama.cpp ARCH=cuda
install-prism-metal: ## Build+install Prism llama.cpp (Metal; macOS only)
	$(MAKE) build-variant TREE=prism BACKEND=metal
	$(MAKE) venv-install link smoke
install-upstream-metal: ## Build+install upstream llama.cpp (Metal; macOS only)
	$(MAKE) build-variant TREE=upstream BACKEND=metal
	$(MAKE) venv-install link smoke

# ---- container start scripts + post-install version test (issue #98) -------
# `make install` writes a start script per engine image into ~/bin
# (llgenie-engine-<id>) that docker-runs the image with the model mounted, then
# tests each shim's docker binary on --version. The Metal/Apple-Silicon variant
# is the only one not container-tested (it cannot run headless in a container).
# Images come from the CI-published registry: make install PULLS the tested image
# for this host's backend and never builds unless BUILD=1. Default ENGINES = the
# llama.cpp core (llama-server + prism-server); ENGINES=all = every engine; other
# engines are pulled on first use by `llgenie --pick/--engine`.
export LLGENIE_REGISTRY ?= ghcr.io/asimov-agent
engine-launchers: ## Pull this host's published engine images (default: llama.cpp + Prism; ENGINES=all|id,id; BUILD=1 builds unpublished ones), write ~/bin/llgenie-engine-<id> + the llama-server / prism-server shims
	python3 scripts/install_engine_launchers.py --bin "$(BIN)" $(if $(ARCH),--arch $(ARCH),) $(if $(BUILD),--build,) $(if $(ENGINES),--engines $(ENGINES),)
test-built-engine: ## After make install: every ~/bin/llgenie-engine-* start script must print its engine version via docker (Metal-only engines excluded)
	python3 scripts/install_engine_launchers.py --bin "$(BIN)" --test

# ---- engine skills (issue #98) ------------------------------------------
# One SKILL.md per inference server in skills/engines/<id>/. The skills are read
# ONLY by `make generate-engine-params` (and the inspection targets below:
# skills-validate, engine-list/plan/check). Every build target (install,
# build-variant, build-engine, run-engine, test-engine, CI) uses the GENERATED,
# committed files in containers/engines/ and runs with plain make: no LLM, no
# skills needed. tests/test_engine_skills.py builds from a repo copy without skills/.
# REGISTRY defaults to the pinned snapshot; pass the live URL to check drift:
#   make skills-validate REGISTRY=https://raw.githubusercontent.com/andyholst/trending-local-llms/master/data/models.json
REGISTRY ?= tests/fixtures/trending-models.json
ENGINE_ARGS = $(if $(BACKEND),--backend $(BACKEND),)
# ---- trending registry (issue #105) ------------------------------------------
# data/models.json is a verbatim copy of trending-local-llms data/models.json:
# llgenie's trend pick reads it (no live fetch at run time). The registry-sync
# workflow runs `make sync-registry` daily and opens a PR when it changed.
sync-registry: ## Download trending-local-llms data/models.json into data/models.json (validated; written only when changed)
	python3 scripts/sync_registry.py sync
check-registry: ## Validate the vendored data/models.json (CI unit job)
	python3 scripts/sync_registry.py check
sync-quant-catalog: ## Regenerate data/trending-quant-catalog.json + its test fixture (the HF class table llgenie's pick reads) from the REAL registry + live Hub (read-only: lists quant plans + resolve links, never downloads a model; validates the newly-added links vs the prior generated table)
	python3 scripts/gen_trending_quant_catalog.py
check-quant-catalog: ## CI: fail when data/trending-quant-catalog.json differs from what the generator produces (the HF class table is a committed, generator-maintained artifact — not llgenie runtime logic)
	python3 scripts/gen_trending_quant_catalog.py --check
sync-strata-models: ## Write data/strata_models.json from Strata's setup.py at the skill's pinned commit (the GGUF files Strata runs)
	python3 scripts/strata_models.py sync
check-strata-models: ## CI: fail when data/strata_models.json differs from Strata's setup.py at the pinned commit
	python3 scripts/strata_models.py check
skills-validate: ## Validate every engine skill against the trending-local-llms registry
	python3 scripts/engine_skills.py validate --registry "$(REGISTRY)"
engine-list: ## List engine skills (servable, backends, fits this machine)
	python3 scripts/engine_skills.py list
engine-hardware: ## Show the detected hardware parameters skills render against
	python3 scripts/engine_skills.py hardware
engine-plan: ## Render ENGINE's install/launch for this machine (ENGINE=<id> [BACKEND=])
	@test -n "$(ENGINE)" || { echo "Usage: make engine-plan ENGINE=<id> [BACKEND=cuda]"; exit 1; }
	python3 scripts/engine_skills.py plan "$(ENGINE)" $(ENGINE_ARGS)
engine-check: ## Report blockers for installing ENGINE here (ENGINE=<id> [BACKEND=])
	@test -n "$(ENGINE)" || { echo "Usage: make engine-check ENGINE=<id> [BACKEND=cuda]"; exit 1; }
	python3 scripts/engine_skills.py check "$(ENGINE)" $(ENGINE_ARGS)
engine-install: ## Install ENGINE via its skill (ENGINE=<id> [BACKEND=] [DRY=1])
	@test -n "$(ENGINE)" || { echo "Usage: make engine-install ENGINE=<id> [BACKEND=cuda] [DRY=1]"; exit 1; }
	python3 scripts/engine_skills.py install "$(ENGINE)" $(ENGINE_ARGS) $(if $(DRY),--dry,)
# ---- engine images: one per engine x backend x GPU arch -------------------
# Two steps, never mixed, no LLM needed for either:
#   1. make generate-engine-params  skills -> containers/engines/params/<engine>.json
#      (FIXED build/run parameters per backend: cpu, cuda, rocm, vulkan; GPU
#      code is a fat build covering CUDA 75..120 / ROCm gfx1030..gfx1201) AND one
#      Dockerfile per engine x backend in containers/engines/dockerfiles/<engine>/
#      Dockerfile.<backend>, plus shared toolchain bases in containers/engines/base,
#      FROM the official upstream image when one exists (vllm/vllm-openai,
#      ollama/ollama, lmsysorg/sglang, nvcr.io tensorrt-llm), else a CUDA/ROCm/
#      ubuntu base with a slim runtime stage. Files change only when the rendered
#      parameters differ. Commit the result.
#   2. make build-engine ENGINE=<id> [ARCH=<variant>]  docker-builds that
#      generated Dockerfile. Skills are not read. The tag hashes the frozen
#      variant, so nothing is rebuilt unless the parameters changed.
# The image serves the OpenAI API on 11434; run-engine publishes it on
# 127.0.0.1:$(PORT) -> base_url http://127.0.0.1:$(PORT)/v1, model llm-local.
PORT ?= 11434
ARCH_ARGS = $(if $(ARCH),--variant $(ARCH),$(ENGINE_ARGS))
generate-engine-params: ## Regenerate containers/engines/params/*.json from the current engine skills (per engine x arch)
	python3 scripts/engine_skills.py params
check-engine-params: ## CI: fail if committed engine params differ from what the skills generate
	python3 scripts/engine_skills.py params --check
build-engine-base: ## Build the shared toolchain base image for BACKEND (cpu|cuda|rocm|vulkan; PUSH=1 publishes + caches in LLGENIE_REGISTRY)
	@test -n "$(BACKEND)" || { echo "Usage: make build-engine-base BACKEND=cpu|cuda|rocm|vulkan [PUSH=1]"; exit 1; }
	python3 scripts/engine_image.py build-base "$(BACKEND)" $(if $(FORCE),--force,) $(if $(PUSH),--push,)
build-engine: ## Build ENGINE's image for one backend from its generated Dockerfile (ARCH=cpu|cuda|rocm|vulkan; FORCE=1, PUSH=1)
	@test -n "$(ENGINE)" || { echo "Usage: make build-engine ENGINE=<id> [ARCH=cpu|cuda|rocm|vulkan]"; exit 1; }
	python3 scripts/engine_image.py build "$(ENGINE)" $(ARCH_ARGS) $(if $(FORCE),--force,) $(if $(PUSH),--push,)
run-engine: ## Run ENGINE's image: OpenAI API on 127.0.0.1:$(PORT)/v1 as llm-local (MODEL=<path under ~/models | HF id>)
	@test -n "$(ENGINE)" -a -n "$(MODEL)" || { echo "Usage: make run-engine ENGINE=<id> MODEL=<path|hf-id> [ARCH=] [PORT=11434]"; exit 1; }
	python3 scripts/engine_image.py run "$(ENGINE)" $(ARCH_ARGS) --model "$(MODEL)" --port "$(PORT)"
test-published-engine: ## Issue #102: pull ENGINE's ARCH image AS PUBLISHED (no build, digest == :ARCH), then (1) the binary reports its version and (2) the container serves the tiny model and answers "hi" on /v1/chat/completions as llm-local (cpu images, and GPU images of engines with a CPU fallback run without GPU devices; GPU-only engines get the version test)
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make test-published-engine ENGINE=<id> ARCH=cpu|cuda|rocm|vulkan"; exit 1; }
	python3 scripts/engine_image.py pull-published "$(ENGINE)" $(ARCH_ARGS)
	$(MAKE) test-engine-image ENGINE=$(ENGINE) ARCH=$(ARCH)
	@if python3 -c 'import sys; sys.path.insert(0, "scripts"); import engine_image as ei; sys.exit(0 if ei.chat_testable("$(ENGINE)", "$(ARCH)") else 1)'; then \
	  python3 scripts/engine_smoke.py "$(ENGINE)" $(ARCH_ARGS) --image $(if $(filter cpu,$(ARCH)),,--no-gpu); \
	else echo "[published] $(ENGINE)/$(ARCH) needs a GPU to serve (no CPU fallback): version test only; its cpu image is chat-tested"; fi
push-engine: ## Push ENGINE's built + tested image to LLGENIE_REGISTRY (GHCR): <registry>/<name>:<pinned-hash-arch> and :<arch>
	@test -n "$(ENGINE)" || { echo "Usage: make push-engine ENGINE=<id> ARCH=cpu|cuda|rocm|vulkan"; exit 1; }
	python3 scripts/engine_image.py push "$(ENGINE)" $(ARCH_ARGS)
stop-engine: ## Stop ENGINE's running container
	@test -n "$(ENGINE)" || { echo "Usage: make stop-engine ENGINE=<id>"; exit 1; }
	python3 scripts/engine_image.py stop "$(ENGINE)" $(ARCH_ARGS)
ci-engine-images: ## Monitor the CI engine-image jobs for the current branch (builds run in CI, not locally)
	@python3 scripts/engine_image.py ci-status $(if $(WATCH),--watch,) $(if $(RUN),--run $(RUN),)
# Per-engine x arch shortcuts, e.g. `make build-engine-vllm-cuda`,
# `make build-engine-llama.cpp-prism-rocm`, `make run-engine-ollama-cpu MODEL=…`.
# The last dash-separated word is the arch (cpu|cuda|rocm|vulkan).
build-engine-%: ## Build one engine x arch image from its generated Dockerfile (build-engine-<engine>-<arch>)
	$(MAKE) build-engine ENGINE=$(patsubst %-$(lastword $(subst -, ,$*)),%,$*) ARCH=$(lastword $(subst -, ,$*))
run-engine-%: ## Run one engine x arch image (run-engine-<engine>-<arch> MODEL=…)
	$(MAKE) run-engine ENGINE=$(patsubst %-$(lastword $(subst -, ,$*)),%,$*) ARCH=$(lastword $(subst -, ,$*))
build-engines: ## Build every engine image for ARCH (cpu|cuda|rocm|vulkan) from the generated Dockerfiles
	@test -n "$(ARCH)" || { echo "Usage: make build-engines ARCH=cpu|cuda|rocm|vulkan [PUSH=1]"; exit 1; }
	@for e in $$(python3 scripts/engine_image.py matrix --json | python3 -c 'import json,sys;print(" ".join(r["engine"] for r in json.load(sys.stdin)["include"] if r["variant"]=="$(ARCH)"))'); do \
		$(MAKE) build-engine ENGINE=$$e ARCH=$(ARCH) $(if $(PUSH),PUSH=1,) || exit 1; done
generate-build-engine-params: generate-engine-params ## Alias of generate-engine-params
list-engine-images: ## List every engine x arch variant (CI=1: only CI variants, JSON=1: GitHub matrix JSON)
	@python3 scripts/engine_image.py matrix $(if $(CI),--ci,) $(if $(JSON),--json,)
test-engine-image: ## GPU images on GPU-less CI: run tests/test_engine_version.py (entrypoint `version`; needs a GPU to serve)
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine-image ENGINE=<id> ARCH=cuda|rocm|vulkan"; exit 1; }
	python3 scripts/engine_image.py test-image "$(ENGINE)" $(ARCH_ARGS)
	@mkdir -p "$(CI_HOME)"
	$(call engine_test,LLGENIE_TEST_ENGINE="$(ENGINE)" LLGENIE_TEST_ARCH="$(ARCH)") \
		python3 -m pytest -q -p no:cacheprovider tests/test_engine_version.py
	@$(CI_HOME_CLEAN)
test-engine: ## Run ENGINE's image with a tiny model and curl its OpenAI API on the published port
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine ENGINE=<id> [ARCH=cpu-portable]"; exit 1; }
	python3 scripts/engine_smoke.py "$(ENGINE)" $(ARCH_ARGS) --image
engine-smoke: ## Install ENGINE via its skill, serve a tiny model, assert llm-local answers (CI engine-smoke job)
	@test -n "$(ENGINE)" || { echo "Usage: make engine-smoke ENGINE=<id> [BACKEND=cpu]"; exit 1; }
	python3 scripts/engine_smoke.py "$(ENGINE)" $(ENGINE_ARGS)
engine-detect: ## Is ENGINE installed? Runs the skill's detect (ENGINE=<id> [BACKEND=])
	@test -n "$(ENGINE)" || { echo "Usage: make engine-detect ENGINE=<id> [BACKEND=cuda]"; exit 1; }
	python3 scripts/engine_skills.py detect "$(ENGINE)" $(ENGINE_ARGS)

# ---- helpers ------------------------------------------------------------
list:
	@$(LAUNCHER) --list

generate-requirements: ## Recompile tools/requirements.in -> tools/requirements.txt (container or venv pip-compile)
	$(MAKE) -C tools generate-requirements

version: ## Show numpy/gguf versions inside the venv
	$(MAKE) -C tools version

# ---- OpenSpec (Dockerized CLI) --------------------------------------------
# The OpenSpec CLI runs inside the openspec/ container with the repo mounted at
# /repo, so `make openspec-new` etc. create/validate openspec/changes/<name> in
# this repository. This is the checklist-of-record for agent work: every step
# you implement maps to a task in openspec/changes/<name>/tasks.md.

openspec-image: ## The OpenSpec CLI image: pull the published hash of openspec/Dockerfile (GHCR), else build it here (issue #117)
	python3 scripts/ci_images.py ensure openspec

openspec-image-pull: ## CI: pull the published OpenSpec image (hash of openspec/Dockerfile) as $(OS_IMG); fails if not published, never builds
	python3 scripts/ci_images.py pull openspec

OS_OPTS := --rm -u root -v "$(REPO)":/repo:rw -w /repo $(OS_IMG)
# Same pin as openspec/Dockerfile ARG OPENSPEC_VERSION. macOS has no Docker, so
# openspec-validate installs this CLI instead of `docker run` (issue #120).
OPENSPEC_VERSION := 1.10.0

openspec-new: openspec-image ## openspec new change <NAME>
	@test -n "$(NAME)" || { echo "Usage: make openspec-new NAME=<kebab-name>"; exit 1; }
	$(RUNTIME) run $(OS_OPTS) openspec new change $(NAME)

openspec-validate: ## openspec validate <NAME>  (fail-closed gate used by the loop)
	@test -n "$(NAME)" || { echo "Usage: make openspec-validate NAME=<change>"; exit 1; }
	@if [ "$(HOST_OS)" = Darwin ]; then \
	  command -v openspec >/dev/null 2>&1 || npm install -g @fission-ai/openspec@$(OPENSPEC_VERSION); \
	  openspec validate $(NAME); \
	else $(RUNTIME) run $(OS_OPTS) openspec validate $(NAME); fi

openspec-tasks-check: ## Assert all ACTIVE OpenSpec changes have no unchecked task checkboxes (NAME=<change> to check one). Fails CI when a task is left `- [ ]`. Pure-python host-side (no container needed).
	@python3 scripts/check_openspec_tasks.py $(NAME)

openspec-status: ## openspec status
	$(RUNTIME) run $(OS_OPTS) openspec status

openspec-shell: ## Interactive shell into the repo with the openspec CLI
	$(RUNTIME) run --rm -it -v "$(REPO)":/repo:rw -w /repo $(OS_IMG) /bin/sh

# ---- Tests (containerized — run identically on host nerdctl and CI docker) --
# The test image bundles python + pytest + all deps; the repo is mounted at
# /repo and llama-server is resolved via $LLAMA_SERVER (host LLAMA_BIN or CI
# build). Bare `run` (like the openspec targets) avoids compose's `--tty`
# console requirement under non-interactive make.
TEST_IMG := llgenie/test:latest
# A git WORKTREE stores its metadata in the PARENT repo's .git/worktrees/<name>
# dir; mounting only the worktree at /repo leaves `git ls-files` broken inside
# the container (it can't resolve the gitdir), which fails the hermetic lint
# regression tests. Detect a worktree (`.git` is a FILE, not a dir) and also
# mount the parent repo at its real path so `git` works. A normal checkout (CI)
# has `.git` as a DIR -> GIT_WORKTREE_PARENT is empty -> no extra mount, so CI
# is byte-identical to before.
GIT_WORKTREE_PARENT := $(shell sed -nE 's|^gitdir: +||p' .git 2>/dev/null | sed 's|/.git/worktrees/.*||')
WORKTREE_MOUNT := $(if $(GIT_WORKTREE_PARENT),-v "$(GIT_WORKTREE_PARENT)":$(GIT_WORKTREE_PARENT):rw,)
TEST_OPTS := --rm -u root -v "$(REPO)":/repo:rw -w /repo -e HOME=/root -e HF_TOKEN $(WORKTREE_MOUNT)
# Install/health tests start engine images through the HOST docker. The install
# HOME lives inside the repo mount at the SAME path on host and in the container,
# so bind mounts the container asks the host docker for (-v <models>:/models)
# resolve on the host. --network host lets the tests reach the published ports.
CI_HOME := $(REPO)/.ci-home
# Python 3.11 everywhere (issue #120): Linux runs the test stages in llgenie/test
# (python:3.11-slim); macOS runs the SAME commands natively in the 3.11 gguf venv
# ($(VENV), built by `make test-env` -> tools venv-dev-install), never in a container.
# `$(call engine_test,K=V ...)` = the engine-test runner with extra env vars.
HOST_OS := $(shell uname -s)
ifeq ($(HOST_OS),Darwin)
VENV_GUARD := test -x "$(VENV)/bin/python" || { echo "ERROR: no Python 3.11 venv at $(VENV): run 'make test-env'"; exit 1; } &&
TEST_RUN := $(VENV_GUARD) env PATH="$(VENV)/bin:$$PATH"
engine_test = $(VENV_GUARD) env HOME="$(CI_HOME)" RUNTIME=docker PATH="$(VENV)/bin:$$PATH" $(1)
ENGINE_TEST_RUN := $(call engine_test,)
CI_HOME_CLEAN := rm -rf "$(CI_HOME)"
else
ENGINE_TEST_ARGS := $(RUNTIME) run --rm -u root --network host \
	-v /var/run/docker.sock:/var/run/docker.sock -v "$(REPO)":"$(REPO)":rw -w "$(REPO)" \
	-e HOME="$(CI_HOME)" -e LLGENIE_REGISTRY -e HF_TOKEN -e RUNTIME=docker $(WORKTREE_MOUNT)
engine_test = $(ENGINE_TEST_ARGS) $(foreach v,$(1),-e $(v)) $(TEST_IMG)
ENGINE_TEST_RUN := $(call engine_test,)
# .ci-home is written by root inside the container: remove it from a container too.
CI_HOME_CLEAN := $(RUNTIME) run --rm -v "$(REPO)":/r $(TEST_IMG) rm -rf /r/.ci-home
TEST_RUN := $(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)
endif

test-env: ## The Python 3.11 test environment: Linux pulls llgenie/test (python:3.11-slim); macOS builds the 3.11 gguf venv + dev deps and puts uv on PATH (no container)
ifeq ($(HOST_OS),Darwin)
	$(MAKE) -C tools venv-dev-install
	@command -v uv >/dev/null || brew install uv
	@command -v uv >/dev/null
else
	python3 scripts/ci_images.py pull test
endif

# CUDA-toolkit (nvcc) + python image for the #84/#89 variant builds. The same
# image does all ubuntu-latest CPU + CUDA builds: builds use nvcc, and the
# 0.5B "hi" health check uses the bundled python + gguf/numpy/hf. (Metal builds
# run on macos-14 host toolchains — see the ci.yml jobs.)
VARIANT_IMG := gguf-tools/ci-variant:latest
VARIANT_RUN := $(RUNTIME) run $(VARIANT_OPTS) $(VARIANT_IMG)

test-image: ## The test image: pull the published hash of its Dockerfile + lockfiles (GHCR), else build it here (issue #117)
	python3 scripts/ci_images.py ensure test

test-image-pull: ## CI: pull the published test image (hash of its Dockerfile + lockfiles) as $(TEST_IMG); fails if not published, never builds
	python3 scripts/ci_images.py pull test

publish-ci-images: ## CI job ci-images: build + push the test and OpenSpec images (linux/amd64 + arm64) ONLY when their hash tag is not on GHCR yet
	python3 scripts/ci_images.py publish test openspec

ci-image-refs: ## Print the GHCR refs of the CI images for the current Dockerfiles + lockfiles
	@python3 scripts/ci_images.py ref

test-variant-image: ## Build the CUDA toolkit + python variant-build image for CI variant builds
	@cp tools/requirements.txt tools/requirements-dev.txt containers/ci-variant/
	$(RUNTIME) build -t $(VARIANT_IMG) containers/ci-variant/
	@echo "Variant image built: $(VARIANT_IMG)"

test-clean: ## Remove left-over/stopped orphaned containers of the test image (interrupted/failed runs)
	# Docker/nerdctl-agnostic: list all containers referencing the test image
	# (name format is <random>-test-id), stop+remove ONLY the stopped/left-over
	# ones -- never kill a currently-running test (e.g. an in-progress health
	# check). Never uses `--filter ancestor` (docker lacks it).
	@containers=$$($(RUNTIME) ps -a -q 2>/dev/null); \
	for c in $$containers; do \
	  info=$$($(RUNTIME) inspect -f '{{.Image}}' $$c 2>/dev/null || echo ""); \
	  if printf '%s' "$$info" | grep -q "llgenie/test"; then \
	    running=$$($(RUNTIME) inspect -f '{{.Running}}' $$c 2>/dev/null || echo "false"); \
	    if printf '%s' "$$running" | grep -qi "false"; then \
	      $(RUNTIME) rm -f $$c 2>/dev/null; \
	    fi; \
	  fi; \
	done; \
	echo "Pruned stopped orphaned $(TEST_IMG) containers."

test-unit: ## Hermetic unit tests (containerized) — includes the lint regression + openspec-tasks-check tests
	$(TEST_RUN) python -m pytest tests/test_llama_ai.py tests/test_hf_download_stall.py tests/test_lint_linefeeds.py tests/test_watchloop_dispatch.py tests/test_check_openspec_tasks.py tests/test_install_watchloop_cron.py tests/test_watch_report.py tests/test_ci_variant_matrix.py tests/test_serve_variant.py tests/test_ensure_user_path.py tests/test_engine_skills.py tests/test_detect_server.py tests/test_model_engine_pick.py tests/test_trend_pick.py tests/test_strata_download.py tests/test_macos_install.py tests/test_ci_images.py tests/test_mac_trend_pick.py tests/test_trend_list_acceptance.py tests/test_tensorfold_seamless.py tests/test_pick_matrix.py tests/test_pick_matrix_arch_perms.py tests/test_pick_full_registry.py tests/test_trending_quant_catalog.py tests/test_engine_supported_quants.py tests/test_quant_generator_edges.py tests/test_check_python_uv.py -p no:cacheprovider -q

test-agents-e2e: ## REAL end-to-end agent tests (containerized) — runs ONLY *_e2e*.py files directly
	# issue #63 CI gate: exercises the REAL dispatcher spawn/kill/respawn against a fake
	# worker that does README issue-work, all within a minute. Only tests/*_e2e*.py run
	# (glob, so any future e2e file is picked up automatically).
	$(TEST_RUN) sh -c 'python -m pytest tests/*_e2e*.py -p no:cacheprovider -q'

# hermes-agent needs Python >=3.11, it pins its own 3.12 (gguf venv + test image are 3.11): the guard
# gets its own Python 3.12 venv, built by make on any host (Linux, macOS, CI). It lives
# outside the repo: tests/test_agents_read.py rejects a hermes module imported from the repo.
PY312             ?= python3.12
AGENTS_READ_VENV  ?= $(HOME)/.cache/llgenie/agents-read-venv
HERMES_AGENT_PIN  := hermes-agent==0.19.0

AGENTS_READ_STAMP := $(AGENTS_READ_VENV)/.installed-$(HERMES_AGENT_PIN)

agents-read-venv: $(AGENTS_READ_STAMP) ## Build the Python 3.12 venv for test-agents-read (hermes-agent + pytest); rebuilt only when missing or the pin changes

$(AGENTS_READ_STAMP):
	@command -v $(PY312) >/dev/null 2>&1 || { echo "ERROR: $(PY312) not found (macOS: brew install python@3.12; Linux: apt install python3.12-venv)"; exit 1; }
	@echo "==> Building $(AGENTS_READ_VENV) with $(PY312) ($(HERMES_AGENT_PIN) + pytest)"
	@rm -rf "$(AGENTS_READ_VENV)"
	$(PY312) -m venv "$(AGENTS_READ_VENV)"
	"$(AGENTS_READ_VENV)/bin/python" -m pip install --quiet --no-cache-dir "$(HERMES_AGENT_PIN)" pytest
	@touch "$@"

test-agents-read: agents-read-venv ## Guard: AGENTS.md must not match Hermes context-file threat patterns (fail-closed), then the guard's own tests. Runs in the make-built Python 3.12 venv (agents-read-venv); not containerized, so hermes-agent stays isolated from the 3.11 test image.
	@echo "==> test-agents-read: scanning AGENTS.md with the hermes-agent threat scanner ($(AGENTS_READ_VENV))"
	"$(AGENTS_READ_VENV)/bin/python" scripts/scan_agents_md.py AGENTS.md
	"$(AGENTS_READ_VENV)/bin/python" -m pytest tests/test_agents_read.py --noconftest -p no:cacheprovider -q

test-install: ## Host install tests (containerized) — skips cleanly without artifacts
	$(TEST_RUN) python -m pytest tests/test_install.py -p no:cacheprovider -q

# Native (non-container) engine tests are hardware-scoped (issue #114): only Metal runs
# natively, so they have test cases only on an Apple-Silicon Mac. On any other host
# (every Linux CI job, cuda/rocm/vulkan/cpu) these targets have no case for that
# hardware and say so; the Linux engines are tested through their images instead.
# NATIVE_HOST= simulates a non-Metal host.
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

test-install-ci: ## In the test container: REAL make install (engine images via host docker) -> test-built-engine -> install tests -> "hi" through the container llama-server -> trend pick -> uninstall (NO SKIP). The same on Linux and macOS (CI linux / macos pipelines)
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
	@test -f scripts/llama_serve.py || { echo "FAIL: repo touched"; exit 1; }
	@echo "==> uninstall removed every installed file, no engine container left"

test-health-host: ## After make install: llgenie serves the 0.5B model through ~/bin/llama-server (the llama.cpp image) and answers "hi"
	@HF_BIN="$${HF_BIN:-$$(command -v hf)}" $(PY) scripts/download_test_model.py
	$(PY) -m pytest tests/test_health.py -p no:cacheprovider -q -s

test-install-trend: ## After make install: ~/bin/llgenie with no model in a pty -> recommended list from data/models.json -> pick 1/1 -> real GGUF download -> engine container answers "hi" (issue #105)
	$(PY) -m pytest tests/test_install_trend.py -p no:cacheprovider -q -s

test-install-published: ## After CI published the images: in the test container, make install for BACKEND (mocked via LLAMA_BACKEND; GPU images on CPU) pulls ONLY that backend's published images, llgenie answers "hi" through llama-server and prism-server, --pick --engine pulls the picked engine on first use, the installed llgenie with no model (pty) picks the top trend model + engine, downloads the full GGUF and answers "hi" (issue #105), make uninstall leaves nothing
	@test -n "$(BACKEND)" || { echo "Usage: make test-install-published BACKEND=cpu|cuda|rocm|vulkan"; exit 1; }
	@mkdir -p "$(CI_HOME)"
	$(call engine_test,LLAMA_BACKEND=$(BACKEND) LLGENIE_NO_GPU=1) sh -c 'HF_BIN=$$(command -v hf) python3 scripts/download_test_model.py && python3 -m pytest tests/test_install_published.py -p no:cacheprovider -q -s'
	@$(CI_HOME_CLEAN)

test-top-tier: ## REAL top-tier acceptance (no mocks): live HF trending + fit gate + provider-aware download + placement
	# Host-side acceptance for --download-top-tier (issue #49): hits the live
	# Hugging Face API, the real `hf` downloader, and the real card's memory.
	# Set HF_BIN=/abs/path/to/hf when `hf` is not on PATH.
	@echo "==> Running top-tier acceptance tests (real, no mocks)"
	@HF_BIN="$${HF_BIN:-$(shell command -v hf || echo $(HOME)/models/hf-env/bin/hf)}" \
		$(PY) -m pytest tests/test_top_tier_acceptance.py -p no:cacheprovider -q -m acceptance

test-top-tier-ci: ## REAL top-tier acceptance inside the test container (CI/CPU). `hf` + gguf are bundled in the image.
	# Pin a deterministic card size (16 GB, the documented LLAMA_RAM_BYTES override) so the
	# fit gate deterministically offers top-tier models on any CI runner regardless of its
	# actual free RAM — still a REAL `hf` download, no mock. On the dev host use `test-top-tier`
	# (no pin) so it uses the real card.
	$(TEST_RUN) sh -c 'LLAMA_RAM_BYTES=17179869184 python -m pytest tests/test_top_tier_acceptance.py -p no:cacheprovider -q -m acceptance'

test-top-tier-serve: ## Download a lightweight top-tier model, load it, answer 'hi', check RAM (host GPU or CPU).
	# End-to-end serve proof for the downloaded top-tier model: real lightweight download,
	# launch llama-server, /health, POST "hi" (assert reply), re-measure RAM for headroom.
	@echo "==> Serving a downloaded lightweight top-tier model and answering 'hi'"
	@HF_BIN="$${HF_BIN:-$(shell command -v hf || echo $(HOME)/llama-gguf-tools/.venv/bin/hf)}" \
		$(PY) -m pytest tests/test_top_tier_serve.py -p no:cacheprovider -q -s -m acceptance

test-top-tier-serve-ci: ## Linux: serve the lightweight model through the llama.cpp image. macOS: no engine image (issue #120)
ifeq ($(HOST_OS),Darwin)
	@echo "==> macOS top-tier serve: native Metal only; no engine image is started"
	@python3 scripts/install_engine_launchers.py --bin "$(CI_HOME)/bin" --arch cpu; rc=$$?; \
	  test $$rc -ne 0 || { echo "FAIL: macOS --arch cpu must be refused"; exit 1; }
else
	@mkdir -p "$(CI_HOME)"
	$(ENGINE_TEST_RUN) sh -c 'python3 scripts/install_engine_launchers.py --bin ~/bin --arch cpu --build --engines llama.cpp && LLAMA_SERVER=$$HOME/bin/llama-server python3 -m pytest tests/test_top_tier_serve.py -p no:cacheprovider --basetemp=$$HOME/pytest-tmp -q -s -m acceptance'
	@$(CI_HOME_CLEAN)
endif

test-top-tier-cli-ci: ## REAL CLI dry-run in the test container: llgenie --download-top-tier [--family] --dry (no download/network writes)
	# Run the ACTUAL launcher entry point end-to-end with --dry, verifying the real
	# dispatch (main -> _main_download_top_tier), dynamic card readout, and the ranked
	# preview — no download and no server start. Deterministic card via LLAMA_RAM_BYTES.
	# The --family variant (issue #61) previews a known low-end family (1 provider)
	# the same way — a real HF family search, still no download.
	$(TEST_RUN) python -m pytest tests/test_top_tier_acceptance.py::test_cli_download_top_tier_dry_run_detailed tests/test_top_tier_acceptance.py::test_family_dry_run_known_lowend_one_provider -p no:cacheprovider -q -s -m acceptance

test-health: ## Linux: 0.5B answers "hi" through the llama.cpp engine image. macOS: native Metal only, no image (issue #120)
ifeq ($(HOST_OS),Darwin)
	@echo "==> macOS health: native Metal only; no engine image is pulled and --arch cpu is refused"
	@python3 scripts/install_engine_launchers.py --bin "$(CI_HOME)/bin" --arch cpu; rc=$$?; \
	  test $$rc -ne 0 || { echo "FAIL: macOS --arch cpu must be refused"; exit 1; }
else
	@mkdir -p "$(CI_HOME)"
	$(ENGINE_TEST_RUN) sh -c 'python3 scripts/install_engine_launchers.py --bin ~/bin --arch cpu --build --engines llama.cpp && make venv-install link && make -C tools venv-dev-install && make test-health-host'
	@$(CI_HOME_CLEAN)
endif

test: ## Full fast suite (unit + install; containerized)
	$(TEST_RUN) python -m pytest tests/test_llama_ai.py tests/test_install.py tests/test_lint_linefeeds.py -p no:cacheprovider -q

download-test-model: ## Fetch the lightweight (0.5B Q4 ~340MB) model into container ~/models/Qwen/8GB
	$(TEST_RUN) python scripts/download_test_model.py

lint: ## Lint: fail closed if any tracked text file lacks a trailing newline, or a markdown heading is not preceded by a blank line
	$(TEST_RUN) python scripts/lint_linefeeds.py

lint-fix: ## Append a missing trailing newline (containerized)
	$(TEST_RUN) python scripts/lint_linefeeds.py --fix

loop: loop-harness ## alias
loop-harness: bash-check ## Loop runner (host orchestration): image->download->lint->unit->install->health->test->openspec
	# The harness orchestrates the other stages by shelling out to `make`, so it
	# MUST run on the host (where make + nerdctl/docker live), NOT inside the
	# test container. It only needs python stdlib.
	@python3 scripts/loop_harness.py

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

# ---- watch-loop host crontab install/uninstall (issue #65) ----------------
# The self-driving loop (scripts/watchloop_dispatch.py) needs a `*/20 * * * *`
# host crontab entry. These targets install/uninstall it idempotently, preserving
# unrelated crontab lines, via scripts/install_watchloop_cron.py (per-OS python).
cron-install: ## Install the */20 watch-loop host crontab entry (idempotent, preserves unrelated lines)
	@python3 scripts/install_watchloop_cron.py install $(if $(PYTHON),--python $(PYTHON),)

cron-uninstall: ## Remove ONLY the watch-loop host crontab entry (preserves unrelated lines)
	@python3 scripts/install_watchloop_cron.py uninstall

cron-snapshot: ## Preview the watch-loop crontab entry (no changes)
	@python3 scripts/install_watchloop_cron.py snapshot

watch-report: ## Human-readable watch-loop status report (host-side, reads .watchloop logs + live gh state; WINDOW=N sets dispatch-log window, WATCHLOOP=<dir> points at a fixture .watchloop tree)
	@python3 scripts/watch_report.py $(if $(WINDOW),--window $(WINDOW),) $(if $(WATCHLOOP),--watchloop $(WATCHLOOP),)

# ---- ci-<job>: ONE make target per CI pipeline job (issue #117) -------------
# pipeline.yml runs each as one job, on Linux AND on macOS (issue #120: the same
# file, no combined jobs). The commands are the same on both OSes. Every target
# that runs in a container needs the pulled llgenie/test (or llgenie/openspec) image:
# CI pulls it first with `make test-image-pull` / `make openspec-image-pull`.
ci-lint: bash-check ## CI job lint: make lint
	$(MAKE) lint

ci-unit: bash-check ## CI job unit: hermetic unit tests + registry / skill / Strata / engine-param / quant-catalog checks
	$(MAKE) test-unit
	$(MAKE) skills-validate
	$(MAKE) check-registry
	$(MAKE) check-strata-models
	$(MAKE) check-quant-catalog
	$(MAKE) skills-validate REGISTRY=data/models.json
	$(MAKE) check-engine-params

ci-cron: bash-check ## CI job cron: the real make cron-* targets against a fake crontab (issue #67)
	$(MAKE) cron-snapshot
	@set -eu; \
	export CRONTAB_CMD="$(CURDIR)/tests/fixtures/fake-crontab.sh"; \
	export FAKE_CRONTAB_FILE="$$(mktemp)"; \
	echo "seed unrelated line" > "$$FAKE_CRONTAB_FILE"; \
	$(MAKE) cron-install; \
	$(MAKE) cron-install; \
	test "$$(grep -c '^\*/20' "$$FAKE_CRONTAB_FILE")" = "1" || { echo "FAIL: expected exactly 1 */20 line"; exit 1; }; \
	grep -q "seed unrelated line" "$$FAKE_CRONTAB_FILE" || { echo "FAIL: unrelated line lost"; exit 1; }; \
	$(MAKE) cron-uninstall; \
	if grep -q '^\*/20' "$$FAKE_CRONTAB_FILE"; then echo "FAIL: */20 line still present"; exit 1; fi; \
	grep -q "seed unrelated line" "$$FAKE_CRONTAB_FILE" || { echo "FAIL: unrelated line lost on uninstall"; exit 1; }; \
	rm -f "$$FAKE_CRONTAB_FILE"; \
	echo "CRON MAKE-TARGETS OK: install idempotent, uninstall preserves unrelated"

ci-watch-report: bash-check ## CI job watch-report: the real make watch-report against a fixture .watchloop tree + fake gh shim
	@set -eu; \
	fakebin="$$(mktemp -d)"; \
	cp tests/fixtures/watch-report/fake-gh.sh "$$fakebin/gh"; \
	chmod +x "$$fakebin/gh"; \
	export PATH="$$fakebin:$$PATH"; \
	export WATCH_REPORT_FIXTURE_ROOT="$(CURDIR)"; \
	out="$$($(MAKE) -s watch-report WATCHLOOP="$(CURDIR)/tests/fixtures/watch-report")"; \
	rm -rf "$$fakebin"; \
	printf '%s\n' "$$out"; \
	echo "$$out" | grep -q "## LIVE GitHub state" || { echo "FAIL: missing GitHub state section"; exit 1; }; \
	echo "$$out" | grep -q "## Worker sessions" || { echo "FAIL: missing Worker sessions section"; exit 1; }; \
	echo "$$out" | grep -q "## Dispatcher timeline" || { echo "FAIL: missing Dispatcher timeline section"; exit 1; }; \
	echo "$$out" | grep -q "## CI-red reaction" || { echo "FAIL: missing CI-red reaction section"; exit 1; }; \
	echo "$$out" | grep -q "1 FAIL" || { echo "FAIL: expected the fixture's 1 failing CI check to be surfaced"; exit 1; }; \
	echo "WATCH-REPORT MAKE-TARGET OK: command runs and prints all sections"

ci-dispatch-e2e: bash-check ## CI job dispatch-e2e: make test-agents-e2e (real dispatcher spawn/reclaim, README issue-work)
	$(MAKE) test-agents-e2e

ci-agents-read: bash-check ## CI job agents-read: make test-agents-read (Python 3.12 venv -> AGENTS.md scan -> guard tests)
	$(MAKE) test-agents-read

ci-openspec: bash-check ## CI job openspec: validate the OpenSpec changes and assert every active change has all tasks checked
	$(MAKE) openspec-validate NAME=ci-pipeline
	$(MAKE) openspec-tasks-check

ci-cpu-health: bash-check ## CI job cpu-health: Linux answers "hi" through the llama.cpp image; macOS never starts an engine image
	$(MAKE) test-health

ci-top-tier: bash-check ## CI job top-tier: same targets on both OSes (venv on macOS, test image on Linux)
	$(MAKE) test-top-tier-ci && $(MAKE) test-top-tier-serve-ci && $(MAKE) test-top-tier-cli-ci

ci-install: bash-check ## CI job install: prepare the environment, then test make install, the installed llgenie dry run, and make uninstall as separate steps. macOS never runs a container.
	$(MAKE) test-env
	$(MAKE) ci-install-run
	$(MAKE) ci-install-dry
	$(MAKE) ci-install-uninstall

ci-install-run: bash-check ## make install, as-is (Linux: inside the test container; macOS: the 3.11 venv, no container)
ifeq ($(HOST_OS),Darwin)
	$(MAKE) install
else
	$(ENGINE_TEST_RUN) sh -c 'make install ARCH=cpu'
endif

ci-install-dry: bash-check ## the installed main command, dry run, in the same home make install wrote (does not start a server)
ifeq ($(HOST_OS),Darwin)
	@"$(BIN)/llgenie" --dry
else
	$(ENGINE_TEST_RUN) sh -c '$$HOME/bin/llgenie --dry'
endif

ci-install-uninstall: bash-check ## make uninstall, as-is, then prove nothing of ours is left
ifeq ($(HOST_OS),Darwin)
	@touch "$(BIN)/not-ours"
	$(MAKE) uninstall
	$(MAKE) test-uninstalled
	@test -e "$(BIN)/not-ours" && rm -f "$(BIN)/not-ours"
else
	$(ENGINE_TEST_RUN) sh -c 'touch ~/bin/not-ours && make uninstall && make test-uninstalled && test -e ~/bin/not-ours'
endif

ci-engines: bash-check ## CI engine stage, the ONLY per-OS row (issue #120): BACKEND=cpu|cuda|rocm|vulkan -> make test-install-published (container engines), BACKEND=metal -> each native-Metal engine installed + "hi" on Metal (scripts/ci_engines.py)
	@test -n "$(BACKEND)" || { echo "Usage: make ci-engines BACKEND=cpu|cuda|rocm|vulkan|metal"; exit 1; }
	python3 scripts/ci_engines.py $(BACKEND)

ci-free-disk: ## CI: free runner disk for the large engine images (Linux runner: drop preinstalled SDKs; macOS runner: report only)
	@if [ "$$(uname -s)" = Linux ]; then sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL; \
	else echo "[ci-free-disk] $$(uname -s) runner: nothing to free"; fi
	@df -h /

test-engine-stage: ## CI engine-image post-build test, ONE step for every image: TEST=serve -> make test-engine (OpenAI API answers), TEST=detect -> make test-engine-image (engine version)
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect"; exit 1; }
	@case "$(TEST)" in \
	  serve)  $(MAKE) test-engine ENGINE="$(ENGINE)" ARCH="$(ARCH)" ;; \
	  detect) $(MAKE) test-engine-image ENGINE="$(ENGINE)" ARCH="$(ARCH)" ;; \
	  *) echo "[test-engine-stage] TEST must be serve or detect, got '$(TEST)'"; exit 1 ;; \
	esac

help:
	@echo "Engine images (issue #98, plain make, no LLM):"
	@echo "  make generate-engine-params      skills -> containers/engines/{params,dockerfiles,base} (the ONLY step that reads skills)"
	@echo "  make sync-quant-catalog          regenerate data/trending-quant-catalog.json + fixture (the HF class table: model -> engine -> arch + real quant plans), from the registry + live Hub; validates the newly-added links vs the prior generated table"
	@echo "  make check-quant-catalog         CI: fail if the committed quant catalog differs from what the generator produces"
	@echo "  make build-engine ENGINE=<id> [ARCH=cpu|cuda|rocm|vulkan] [PUSH=1]   build from the generated Dockerfile"
	@echo "  make build-engine-<id>-<arch>    e.g. build-engine-vllm-cuda, build-engine-llama.cpp-prism-rocm"
	@echo "  make build-engines ARCH=<arch>   every engine for one arch"
	@echo "  make run-engine ENGINE=<id> MODEL=<m> [PORT=11434]   OpenAI API at http://127.0.0.1:PORT/v1 (llm-local)"
	@echo "  make list-engine-images | ci-engine-images [WATCH=1]"
	@echo
	@echo "Targets:" \
		"install (venv+launcher+symlink+smoke), venv-install, link, smoke,"
	@echo "         test-unit, test-agents-e2e (real agent e2e), test-install, test-health (endpoint answers 'hi'), test,"
	@echo "         download-test-model, openspec-validate, openspec-new/status,"
	@echo "         loop (chained runner), loop-harness, chained, uninstall,"
	@echo "         cron-install, cron-uninstall, cron-snapshot (watch-loop host crontab),"
	@echo "         watch-report (human-readable watch-loop status report)"
	@echo
	@echo "Install (issue #98: engines run from their images):"
	@echo "  make install [ENGINES=all|id,id] [ARCH=cpu|cuda|rocm|vulkan] [BUILD=1]   pull this host's tested images + start scripts + version test"
	@echo "  make install-prism-cpu|upstream-cpu|prism-cuda|upstream-cuda   one llama.cpp tree + backend (image)"
	@echo "  make install-prism-metal|upstream-metal                         macOS: native Metal build"
	@echo "  make build-variant TREE=prism|upstream BACKEND=metal            native build (Metal / macOS CI)"
	@echo "  llgenie --pick [model] [--engine e] [--model-file f] [--auto]   pick model + fastest engine image"
	@echo
	@echo "Env seams (override detection):"
	@echo "  LLAMA_SERVER_TREE=prism|upstream   force the llama.cpp tree (else card RAM: <=24GB prism, >24GB upstream)"
	@echo "  LLAMA_BACKEND=cpu|cuda|metal       force the backend (else hardware: Metal/CUDA/CPU)"
	@echo "  LLAMA_RAM_BYTES=<bytes>            force the card RAM used by the tree decision"
	@echo "  SERVER_ROOT=<dir>                  where llama.cpp trees are cloned (default ~/repository/git)"
