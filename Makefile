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
# `REPO` is the CHECKOUT PATH — recipes mount it (`-v "$(REPO)":/repo`), so a `$(if $(REPO),$(REPO),…)`
# fallback can never apply and `gh` gets an absolute path ("expected the \"[HOST/]OWNER/REPO\" format",
# issues #343/#434). `GH_REPO` is the slug every gh-calling recipe uses: the repo's own when `REPO` is
# a path, or a `REPO=owner/name` override (anything that is not a path).
GH_REPO := $(if $(filter /%,$(REPO)),asimov-agent/llgenie,$(REPO))
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

.PHONY: all install venv-install link uninstall smoke list version help test-native-engine test-native-engine-serve test-interactive-tensorfold test-interactive-tensorfold-ci test-unit-network test-engine-install ci-install-product \
	git-identity-apply check-git-identity git-identity-line git-identity-report \
	sweep-concurrency-report \
	openspec-image openspec-new openspec-validate openspec-validate-all openspec-status openspec-shell \
	test test-unit test-agents-read agents-read-venv test-install test-install-ci test-install-host test-install-trend test-health test-health-host download-test-model \
	test-image test-image-pull openspec-image-pull publish-ci-images publish-agent-image agent-image-push-check agent-image agent-image-pull ci-image-refs test-clean lint lint-fix loop loop-harness chained sweep-concurrency-report \
	build-server build-variant serve-variant test-serve-variant stop-serve-variant install-prism-cpu install-upstream-cpu \
	install-prism-cuda install-upstream-cuda install-prism-metal install-upstream-metal \
	sync-registry check-registry skills-validate engine-list engine-hardware engine-plan engine-check engine-install engine-detect engine-smoke test-engine ci-engine-images build-engine-base build-engines generate-build-engine-params test-engine-image push-engine test-published-engine test-install-published engine-launchers test-built-engine test-uninstalled \
	sync-quant-catalog check-quant-catalog render-trend-list-matrix check-trend-list-matrix render-engine-skill-gap check-engine-skill-gap \
	engine-gate-report engine-skill-gap engine-skill-gap-md spawn-engine-skill-issues engine-skill-scaffold registry-change-report sync-change-issue registry-review-brief registry-sync-review registry-review-publish sync-strata-models check-strata-models check-wiring wiring-report check-secret-output secret-output-report \
	secret-scan secret-scan-history secret-scan-self-test \
	queued-alarm issue-cleaner-scan issue-cleaner-apply worktree-report worktree-prune fix-loop fix-loop-image fix-bot-sweep fix-bot-report agent-image-ref issue-bot-dispatch issue-bot-open-pr issue-bot-image ci-requeue-cancelled issue-bot-pr-body-check agent-repo-ownership \
	issue-bot-triage issue-bot-changed issue-bot-verdict issue-bot-gates issue-bot-gates-check implement-issue hermes-smoke agent-jev-preflight jev-preflight-required nerve-profile-check code-review-scan code-review-file rebase-bot-sweep rebase-bot rebase-bot-abort \
	engine-params-review-brief engine-params-review engine-params-review-apply \
	architecture-bot-brief architecture-bot-doc architecture-bot-publish architecture-bot \
	scrub-log \
	check-pr-heads pr-heads-report \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report check-issue-bodies issue-bodies-report auto-merge auto-merge-resolve fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report check-module-names issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report security-scan security-scan-all security-verdict security-issues security-issues-plan check-security-issues security-bot security-bot-pick check-security-bot sbom check-security-scan scanner-image test-scanner-image scanner-digests scanner-ref publish-scanner-images ci-scanner-images check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report scanner-image test-scanner-image scanner-digests scanner-ref publish-scanner-images ci-scanner-images check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-actions actions-report update-actions \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-renovate renovate-report \
	arm-auto-merge arm-auto-merge-report \
	security-bumps security-bumps-plan check-security-bumps \
	agent-shell-keys-check \
	agent-fetch search-smoke require-env web-coverage issue-evidence \
	engine-bump-rebase generate-engine-params check-engine-params check-engine-coverage engine-coverage-report check-engine-source engine-source-report check-engine-launchers engine-launchers-report check-model-links model-links-report build-engine run-engine stop-engine list-engine-images engine-build-matrix ci-lint ci-unit ci-agents-read \
	ci-openspec ci-cpu-health ci-top-tier ci-install ci-install-dry-args ci-free-disk ci-slow-rows test-engine-stage bot-sync-main bot-sync-branch ci-wait-engine-images \
	ci-install-dry ci-install-run ci-install-uninstall test-env test-top-tier test-top-tier-ci test-top-tier-cli-ci test-top-tier-serve test-top-tier-serve-ci \
	check-agent-model model-pin-report check-agent-skills agent-skills-report test-agent-skills-live hermes-skills-register \
	test-hub-live test-strata-live test-engine-bump-live test-native-engines test-native-engine-light test-variant-image \
	bash-check engine-bump engine-bump-daily engine-bump-plan engine-derive generate-requirements openspec-tasks-check check-registry-keys ci-engines

# ---- container runtime: docker -------------------------------------------
RUNTIME ?= docker
OS_IMG := llgenie/openspec:latest

# ---- credentials the AGENT's shell must see (issue #358) --------------------
# Hermes STRIPS provider credentials from its terminal tool on purpose
# (`tools/environments/local_env_policy.py::_STATIC_PROVIDER_ENV_BLOCKLIST`):
# NOUS_API_KEY, GH_TOKEN, FIRECRAWL_API_KEY and HF_TOKEN are on it, and
# `env_passthrough` can never re-allow a blocklisted name. So a key forwarded as
# `-e NOUS_API_KEY` reaches the container and the Hermes process — while the
# agent's own shell reads it EMPTY, which is how a bot does nothing while its step
# log shows the name. The one sanctioned way through is `_HERMES_FORCE_<NAME>`,
# which Hermes's terminal env builder unwraps back to `<NAME>`. Measured on this
# host against the real Hermes: plain names -> `agent-shell=EMPTY` (exit 1),
# forced names -> `agent-shell=set`.
#
# ONE list: every credential a container receives. On the HOST, make exports
# `_HERMES_FORCE_<NAME>` from `<NAME>` BY REFERENCE (the value is never on a
# command line, in a recipe or in a log — so `ps` cannot see it), and only when
# `<NAME>` is set. Inside a container (`/.dockerenv`) nothing is re-created, so
# `make agent-shell-keys-check` proves what `docker run` forwarded, never what an
# inner make invented. IN_CONTAINER is overridable for the tests only.
AGENT_SHELL_KEYS := NOUS_API_KEY GH_TOKEN HF_TOKEN TYPESAFE_API_KEY FIRECRAWL_API_KEY
AGENT_FORCE_PREFIX := _HERMES_FORCE_
IN_CONTAINER ?= $(if $(wildcard /.dockerenv),1,)
ifeq ($(IN_CONTAINER),)
$(foreach k,$(AGENT_SHELL_KEYS),$(if $(value $(k)),$(eval export $(AGENT_FORCE_PREFIX)$(k) = $$($(k)))))
endif
AGENT_SHELL_FORWARD := $(foreach k,$(AGENT_SHELL_KEYS),-e $(AGENT_FORCE_PREFIX)$(k))
# The plain names too: `docker run` does not inherit the host env, so the container only has
# a key it was explicitly given (the check needs it set in the container to prove anything).
AGENT_SHELL_FORWARD_PLAIN := $(foreach k,$(AGENT_SHELL_KEYS),-e $(k))

# The MARKER every unattended run carries, so `make worktree-prune` refuses it (issue #794).
# `docker run` does not inherit the host environment and the agent image sets no such `ENV`, so a
# bot leg has no `CI`/`BOT` unless the Makefile forwards one. `BOT=1` is deliberately not a
# credential: it is a fact about the run, safe to show on a command line and in a log.
# `tests/test_worktree_report.py` derives the leg roster from this file and fails a run that omits it.
AGENT_BOT_MARKER := -e BOT=1

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
		"$(REPO)/scripts/llgenie_serve.py" "$(VENV)" "$(PY)" "$(REPO)/scripts/llgenie_serve.py" > "$(LAUNCHER)"
	@chmod +x "$(LAUNCHER)"
	@ln -sfn "$(REPO)/scripts/llgenie_serve.py" "$(BIN)/llgenie.py"
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

test-engine-install: bash-check # Internal CI seam (issue #1027, deliberately internal like test-unit-network): after ENGINE's image was built + published in the engine-build producer, install + test-built-engine (the installed launcher must report the engine's version) + llgenie --dry + uninstall the just-published image — the producer-owned install leg. Gating lives in the engine-build workflow (`inputs.push == 'true'`).
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine-install ENGINE=<id> ARCH=<variant>"; exit 1; }
	make engine-install ENGINE="$(ENGINE)" BACKEND="$(ARCH)"
	make test-built-engine
	make ci-install-dry
	make ci-install-uninstall

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
# workflow runs `make sync-registry` weekly (cron 17 5 * * 1) and opens a PR when it changed.
sync-registry: ## Download trending-local-llms data/models.json (+ its README and data/model_contract.json, the contract the store must satisfy) into data/ (validated against that contract; written only when changed)
	python3 scripts/sync_registry.py sync
check-registry: ## Validate the vendored data/models.json against the vendored upstream contract, then fail when the sync LOST anything vs the committed copy (CI unit job)
	python3 scripts/sync_registry.py check
	$(MAKE) check-registry-keys
check-registry-keys: ## Fail when the vendored registry dropped a key, model, measurement, t/s or counter vs the committed copy (additive only)
	python3 scripts/registry_keys.py
sync-quant-catalog: ## Regenerate data/trending-quant-catalog.json + its test fixture (the HF class table llgenie's pick reads) from the REAL registry + live Hub (read-only: lists quant plans + resolve links, never downloads a model; validates the newly-added links vs the prior generated table)
	python3 scripts/gen_trending_quant_catalog.py
check-quant-catalog: ## CI: fail when data/trending-quant-catalog.json differs from what the generator produces (the HF class table is a committed, generator-maintained artifact — not llgenie runtime logic)
	python3 scripts/gen_trending_quant_catalog.py --check
render-trend-list-matrix: ## Rewrite tests/fixtures/trend-list-matrix.json from matrix(registry, vram, ram, arch) for the vendored registry
	python3 scripts/trend_list_matrix.py
check-trend-list-matrix: ## CI: fail when the committed trend-list matrix differs from matrix() on the vendored registry
	python3 scripts/trend_list_matrix.py --check
render-engine-skill-gap: ## Rewrite data/engine-skill-gap.json (per-engine status + the models only unskilled engines serve) from the vendored registry, the skills and the dated decisions
	python3 scripts/engine_skill_gap.py render
check-engine-skill-gap: ## CI: fail when a registry engine has no skill and no dated decision in data/unsupported-engines.json, or when data/engine-skill-gap.json is stale
	python3 scripts/engine_skill_gap.py check
engine-skill-gap: ## Show the unskilled-engine gap: shipped / known-unsupported / new-and-unresolved, the models that can never be offered, and the per-engine list
	python3 scripts/engine_skill_gap.py report

engine-skill-gap-md: ## The same gap report as MARKDOWN, for a PR/issue body (the registry-sync workflow embeds it)
	python3 scripts/engine_skill_gap.py report --md
registry-change-report: ## Print what the working-tree vendored registry changed vs HEAD (models, engines, contract keys, derived tables)
	python3 scripts/registry_change_issue.py report
sync-change-issue: ## Open ONE issue stating what a changed vendored registry changed — updates it in place for the same store (the sync job runs this; DRY=1 previews, REPO= picks the repo)
	python3 scripts/registry_change_issue.py open $(if $(REPO),--repo "$(GH_REPO)",) $(if $(DRY),--dry,)
spawn-engine-skill-issues: ## Open one tracking issue per NEW unskilled registry engine (the sync job runs this; DRY=1 previews, REPO= picks the repo)
	python3 scripts/engine_skill_gap.py spawn $(if $(REPO),--repo "$(GH_REPO)",) $(if $(DRY),--dry,)
engine-skill-scaffold: ## Write skills/engines/<id>/SKILL.md for a registry engine from its registry entry, with every unprovable key left EMPTY (ENGINE=<registry name>, ID=<kebab>, BACKENDS=, OUT=, REGISTRY=, DRY=1 previews, FORCE=1 overwrites)
	python3 scripts/engine_skill_scaffold.py scaffold --engine "$(ENGINE)" \
		$(if $(ID),--id "$(ID)",) $(if $(BACKENDS),--backends "$(BACKENDS)",) \
		$(if $(OUT),--out "$(OUT)",) $(if $(REGISTRY),--registry "$(REGISTRY)",) \
		$(if $(DRY),--dry,) $(if $(FORCE),--force,)
# ---- registry-sync review (issue #709): a GREEN sync PR -> ONE agent:implement issue --------
# sync-change-issue (#704) states what a store CHANGED, even when a gate is red. This bot answers
# the other question, for a store that can LAND: at each VRAM llgenie sells, does the trending list
# list models, and does every row name the inference server with the highest t/s that fits that
# card? The precondition (an open `chore/registry-sync` PR whose every check is green) and the
# selection table are deterministic and offline; the issue body is the one agent leg's (its skill
# is `.hermes/skills/registry-sync-review/SKILL.md`), and publish is the only GitHub writer.
REGISTRY_REVIEW_BRIEF ?= registry-review-in.md
REGISTRY_REVIEW_OUT ?= registry-review.md
registry-review-brief: ## Is the sync PR green, and does the store name the highest-t/s server per card? -> registry-review-in.md (prints action=review|skip and the findings count; read-only; REPO= picks the repo)
	python3 scripts/registry_review.py brief --out "$(REGISTRY_REVIEW_BRIEF)" $(if $(REPO),--repo "$(GH_REPO)",)
registry-sync-review: ## Hermes reviews the green store (reads registry-review-in.md) and writes ONE issue body to registry-review.md; no code, no GitHub write; runs INSIDE the agent image; the transcript is REDACTED (issue #709)
	@python3 scripts/require_env.py NOUS_API_KEY
	@test -f "$(REGISTRY_REVIEW_BRIEF)" || { echo "Run 'make registry-review-brief' first: $(REGISTRY_REVIEW_BRIEF) is missing"; exit 1; }
	@$(MAKE) --no-print-directory agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=NOUS_API_KEY
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _registry-sync-review')
_registry-sync-review: # (internal) the host recipe the agent image runs: the review, not the code
	hermes -z "Follow the preloaded skill registry-sync-review. Its Input is $(REGISTRY_REVIEW_BRIEF) and its Output is $(REGISTRY_REVIEW_OUT), in the shape the skill prints." -s registry-sync-review,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
registry-review-publish: ## File ONE issue labelled agent:implement from registry-review.md, keyed by the store's generated_utc — updates it in place for the same store (REPO=; DRY=1 previews)
	python3 scripts/registry_review.py publish --in "$(REGISTRY_REVIEW_OUT)" $(if $(REPO),--repo "$(GH_REPO)",) $(if $(DRY),--dry,)
# ---- issue-bot: one issue per run, at most 3/day (issue #248) -----------------
# The dispatcher is deterministic (no LLM): cap -> pick ONE -> claim -> issue.md
# + branch. `implement-issue` is the shared Hermes agent step (AGENTS.md is the
# authority the agent reads; #238 wires the token/plugin into the agent image).
# ---- rebase-bot: keep the open PRs on `main` (issue #246). ONE PR per 6-hourly run; a conflict
# is handed to the agent; the result is verified structurally and pushed with --force-with-lease
# to the PR's OWN head remote (a fork PR goes to the fork). It never merges.
rebase-bot-sweep: ## Which ONE open PR needs rebasing (BEHIND/DIRTY against main): prints action/pr/head_* and the reason for every pass-over
	python3 scripts/rebase_bot_sweep.py --repo $(GH_REPO) $(if $(OWN_FORK),--own-fork $(OWN_FORK),) $(if $(SKIP),--skip "$(SKIP)",)

# ---- the model pin the bots call (issue #405) --------------------------------
# The bots run the Hermes CLI in the agent image against ONE pinned snapshot through the alias
# `nous-deepseek`. That pin lives in two build inputs (the Dockerfile's ARG default and the
# install script's MODEL_ID default), and both used to name `deepseek/deepseek-v4.1-flash` —
# the OLDER, different model behind `canonical_slug …-20260910` — while the owner's host alias
# ran the `-1017` snapshot. Nothing compared them, and the one test asserted a substring any
# newer id satisfies. `scripts/agent_model_pin.py` is now the referee: stdlib only, no network,
# no key, and it names the file and the value it read when they disagree.
check-agent-model: ## CI: fail when the agent image's model pin (Dockerfile ARG, install script) is not the one snapshot scripts/agent_model_pin.py declares — or the alias's budget is missing (issue #405)
	python3 scripts/agent_model_pin.py check

model-pin-report: ## Print the bots' pinned model snapshot, where each place declares it, and every finding (issue #405)
	python3 scripts/agent_model_pin.py report

# ---- every bot leg loads its contract from a project skill (issue #577) --------------
# A leg's inline prompt used to be its whole rulebook (1005-1629 characters, the same
# UNATTENDED paragraph seven times). The contract is a Hermes project skill now -
# .hermes/skills/<name>/SKILL.md, the layout Hermes discovers from a trusted checkout - and
# the leg preloads it with `hermes -s <name>`. The gate fails a leg that preloads nothing,
# names a skill that does not exist, carries a name that disagrees with its directory, grows
# past the pointer budget, or inlines the unattended contract again.
.PHONY: bot-preflight
bot-preflight: ## Fetch origin/main, fast-forward a behind checkout, and record the AGENTS.md this run is measured against (issue #792)
	python3 scripts/bot_preflight.py $(if $(CHECK),--check,)

check-agent-skills: ## CI: fail when a bot leg does not preload its project skill, names a missing one, or carries a rulebook inline instead of a pointer (issue #577)
	python3 scripts/check_agent_skills.py check

agent-skills-report: ## Print every agent leg with its prompt size and preloaded skills, and every skill with its frontmatter (issue #577)
	python3 scripts/check_agent_skills.py report

hermes-skills-register: ## Register the checkout's .hermes/skills in Hermes's config so `hermes -s <name>` resolves for every bot leg (HOME_DIR= the Hermes home, DIR= the skill dir; CHECK=1 verifies without writing — issue #577)
	python3 scripts/hermes_skills_register.py --home "$(if $(HOME_DIR),$(HOME_DIR),$(HOME)/.hermes)" --dir "$(if $(DIR),$(DIR),$(CURDIR)/.hermes/skills)" $(if $(CHECK),--check,)


# ---- a leg refuses to start on a missing key (issue #363) --------------------
# A leg that forwards a key its job never set spends the runner first: it pulls the image,
# starts a container, and fails inside Hermes — a 120-180 minute-timeout job lost to a
# plumbing mistake, and a log that reads like a model problem. The guard runs BEFORE
# `ci_images.py ensure agent`, prints the NAME only, and exits 2 (never a skip). The key list
# per leg is the one that leg actually forwards; the suite derives the roster from this file,
# so a new leg without a guard fails the test.
require-env: ## Refuse to start when a credential a leg needs is missing (KEYS="NOUS_API_KEY ..."; name-only, exit 2)
	@test -n "$(KEYS)" || { echo "Usage: make require-env KEYS=\"NOUS_API_KEY [TYPESAFE_API_KEY]\""; exit 1; }
	python3 scripts/require_env.py $(KEYS)

# `$(call …)` splits its arguments on COMMAS IN THE UNEXPANDED TEXT, so a literal `-s a,b` inside
# the call keeps only `-s a`: the rest is dropped, the shell sees an unclosed quote, and the leg dies
# with `unexpected EOF while looking for matching '` before the agent starts (issue #641, measured on
# #602/#605 staying DIRTY). The skills therefore come from a variable — no comma in the call text —
# and `make -n rebase-bot-agent` is the proof.
REBASE_BOT_SKILLS := rebase-conflict,bot-unattended
rebase-bot-agent: ## Ask Hermes to resolve a stopped rebase (the conflict prompt arrives on STDIN); runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm -i --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'hermes -z "$$(cat) Follow the preloaded skill rebase-conflict; the prompt above carries the conflicted files." -s $(REBASE_BOT_SKILLS) $(nous-alias) --reasoning medium --yolo')
# Hermes runs directly there, NOT through `make _rebase-bot-agent`: the container's /repo/Makefile
# is the conflicted file the agent was asked to resolve, and make cannot parse it (issue #460).

rebase-bot-abort: ## Abort a stopped rebase and return the tree to main, so the next decision in the same run starts clean (issue #462)
	@git rebase --abort >/dev/null 2>&1 || true
	@git checkout -q main >/dev/null 2>&1 || true
	@echo "[rebase-bot] abort: tree back on main"

rebase-bot: ## Rebase ONE PR onto main (agent-resolved conflicts), verify the structure, then push --force-with-lease to the PR's head remote. Never merges. Needs PR=/HEAD_BRANCH= [HEAD_REPO=] [DRY=1]
	@test -n "$(PR)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make rebase-bot PR=<n> HEAD_BRANCH=<branch> [HEAD_REPO=<owner>] [REPO=] [DRY=1]"; exit 1; }
	PR=$(PR) HEAD_BRANCH="$(HEAD_BRANCH)" HEAD_REPO=$(if $(HEAD_REPO),$(HEAD_REPO),asimov-agent) \
	  REPO=$(GH_REPO) $(if $(DRY),DRY=1,) scripts/rebase_bot.sh
# ---- issue-refiner: reviews NOT-yet-implemented issues on the implementer's spare capacity
# (issue #263). One issue per run, ONE comment + the `agent:refined` label, and never a PR.
issue-refiner-pick: ## Spare capacity (the implementer's cap is spent)? -> the oldest issue that is not decided, claimed or already PR'd -> refine-in.md (DRY=1 previews; REPO= picks the repo)
	python3 scripts/issue_refiner.py pick --repo $(GH_REPO) $(if $(DRY),--dry,)
issue-refiner: ## Hermes REVIEWS the picked issue (reads refine-in.md: the thread + the review instruction) and writes its verdict to refine.md. No branch, no PR, nothing else touched; runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	@$(MAKE) --no-print-directory agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY
	@$(MAKE) --no-print-directory issue-evidence ISSUE_FILE=refine-in.md OUTDIR=fetched MAX=$(if $(MAX),$(MAX),3)
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _issue-refiner')
_issue-refiner: # (internal) the host recipe the agent image runs: the review, not the code
	hermes -z "Follow the preloaded skill issue-refiner. Its Input is refine-in.md (with fetched/index.md as the pre-fetched evidence) and its Output is refine.md, in the shape the skill prints." -s issue-refiner,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
issue-refiner-apply: ## Apply the review in refine.md: ONE comment on the issue + the agent:refined label (never a PR; refuses a `refined` verdict with no RESTATED block)
	@test -n "$(ISSUE)" || { echo "Usage: make issue-refiner-apply ISSUE=<n> [REPO=<owner/repo>]"; exit 1; }
	python3 scripts/issue_refiner.py apply refine.md --repo $(GH_REPO) --issue $(ISSUE)

issue-dedup-pick: ## Which two unclaimed open issues look like the same defect? -> dedup-in.md, older as canonical (DRY=1 previews; REPO= picks the repo; issue #553)
	python3 scripts/issue_dedup.py pick --repo $(GH_REPO) $(if $(DRY),--dry,)
issue-dedup: ## Hermes decides whether the picked pair is the SAME defect (reads dedup-in.md) and writes dedup.md; no comment, no close, nothing else touched; runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #553)
	@python3 scripts/require_env.py NOUS_API_KEY
	@$(MAKE) --no-print-directory agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=NOUS_API_KEY
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _issue-dedup')
_issue-dedup: # (internal) the host recipe the agent image runs: the decision, not the change
	hermes -z "Follow the preloaded skill issue-dedup. Its Input is dedup-in.md and its Output is dedup.md, in the shape the skill prints." -s issue-dedup,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
issue-dedup-apply: ## Apply dedup.md: retire the COPY with a comment citing the canonical + agent:duplicate, close it, and queue the canonical (COPY=<n>; never touches a claimed issue; refuses a duplicate without EVIDENCE)
	@test -n "$(COPY)" || { echo "Usage: make issue-dedup-apply COPY=<n> [FILE=dedup.md] [REPO=<owner/repo>] [DRY=1]"; exit 1; }
	python3 scripts/issue_dedup.py apply $(if $(FILE),$(FILE),dedup.md) --copy $(COPY) --repo $(GH_REPO) $(if $(DRY),--dry,)

# The documentation review of an engine's DERIVED build parameters (issue #583). The bump proves the
# params COMPILE; this leg checks them against the engine's own docs for the arch being built. The host
# stays the writer: the agent may only propose a `-D` flag whose evidence it quotes from the upstream
# tree at the pin, and the apply step drops anything it cannot find there.
engine-params-review-brief: ## Issue #583: write params-review-in.md — the engine's upstream docs at its pinned sha + the params this repo builds with (deterministic; ENGINE=<id>)
	@test -n "$(ENGINE)" || { echo "Usage: make engine-params-review-brief ENGINE=<id>"; exit 1; }
	python3 scripts/engine_params_review.py brief --engine "$(ENGINE)"
engine-params-review: ## Issue #583: Hermes reviews the derived params against the engine's own documentation and writes params-review.md (may propose only documented -D flags; runs INSIDE the agent image; the transcript is REDACTED before it prints)
	@python3 scripts/require_env.py NOUS_API_KEY
	@$(MAKE) --no-print-directory agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=NOUS_API_KEY
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _engine-params-review')
_engine-params-review: # (internal) the host recipe the agent image runs: the review, not the change
	hermes -z "Follow the preloaded skill engine-params-review. Its Input is params-review-in.md and its Output is params-review.md, in the PROPOSE/NO REVIEW shape the skill prints. Propose only parameters whose flag AND quoted evidence appear in the named upstream file; the host drops anything else." -s engine-params-review,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
engine-params-review-apply: ## Issue #583: validate params-review.md (the flag AND its quote must be in the named upstream file), append accepted flags to the skill, regenerate params/Dockerfiles and write the PR section (ENGINE=; DRY=1 previews, mutating nothing)
	@test -n "$(ENGINE)" || { echo "Usage: make engine-params-review-apply ENGINE=<id> [DRY=1]"; exit 1; }
	python3 scripts/engine_params_review.py apply --engine "$(ENGINE)" $(if $(DRY),--dry,)

issue-bot-dispatch: ## The issue-implementer's dispatcher: cap (3/day) -> pick one labeled/ready issue -> claim -> write issue.md + branch (REPO= issue-bot.yml sets it; FORCE_ISSUE= pins a manual run; DRY=1 previews)
	python3 scripts/issue_implementer.py dispatch --repo "$(GH_REPO)" $(if $(FORCE_ISSUE),--force-issue $(FORCE_ISSUE),) $(if $(DRY),--dry,) $(if $(TODAY),--today $(TODAY),)
issue-bot-open-pr: ## Open the draft-free PR linking ISSUE from BRANCH, its body built from the agent's pr-body.md + the commit's stat and titled from the issue (never merges; refuses a body with missing Issue:/Fix:/Benefit:/Technical: parts; REPO=/ISSUE=/BRANCH= from the workflow)
	@test -n "$(ISSUE)" && test -n "$(BRANCH)" || { echo "Usage: make issue-bot-open-pr REPO=<owner/repo> ISSUE=<n> BRANCH=<agent/issue-n-slug>"; exit 1; }
	python3 scripts/issue_implementer.py open-pr --repo "$(GH_REPO)" --issue $(ISSUE) --branch "$(BRANCH)" --body-file $(if $(BODY_FILE),$(BODY_FILE),pr-body.md)
# The agent step: Hermes reads issue.md + AGENTS.md at the repo root and
# implements it. AGENTS.md is the authority (Makefile-driven verification, no
# skipped tests, business logic never mocked, one make path per stage, wiring).
# Runs on the CI runner with NOUS_API_KEY from a secret; #238 wires the
# token/plugin into the agent image. The model alias matches the sibling repo.
# Hermes's bundled `nous` provider is OAuth-only, so `--provider nous` cannot work with a
# secret. The image's install script writes a custom-provider alias instead (provider=custom,
# base_url=the Nous OpenAI-compatible endpoint, key_env=NOUS_API_KEY) and this is the model
# name every call uses. `-m` is the MODEL flag (a bare `-m "text"` sets the model to text).
nous-model := nous-deepseek
nous-alias := -m $(nous-model)
HERMES_REASONING ?= low
# The bots run INSIDE the agent image (issues #222/#238/#248): Hermes, git, gh and the docker
# CLI are installed when the image is built, so a runner never installs the agent on the fly —
# and the image a job uses is the one built from THIS commit's Dockerfile + install script
# (the ref is their hash, so it cannot drift from the workflow that names it).
# NOUS_API_KEY and GH_TOKEN travel as run-time env; nothing is baked into the image.
# `ensure` pulls the published image of these inputs, or builds the same Dockerfile locally, and
# tags it under this name either way — so this works on a dev host and on a runner. The tag hash
# pins it to the exact Dockerfile THIS commit carries.
# ---- the agent's own transcript is REDACTED before anything prints it (issue #359) ----
# A bot's agent stream IS the job's console output: `make implement-issue` writes whatever
# the agent printed straight into the step log. GitHub masks the secret values it REGISTERS,
# and that is a filter over the stream, not a property of the content — a transformed one
# (URL-encoded, base64, a slice) sails past, and nothing is masked in a log a job uploads
# itself. So every leg captures its stream to $(HERMES_LOG) and prints only the redactor's
# bounded tail; the REDACTED whole log is $(HERMES_LOG_SCRUBBED) (what a workflow uploads as
# its artifact). `scripts/scrub_log.py` reads the secret values BY NAME from this process's
# environment — the runner passes them with `env:`, and the docker call forwards the NAMES —
# so a value the agent printed, in any spelling, never reaches the console.
# ONE seam: the PUBLIC leg recipes below all go through `$(call scrubbed_run,…)`, so a leg
# cannot forget it (the internal recipes run INSIDE the container; their stdout is what the
# public leg captures). Both log files are gitignored.
HERMES_LOG ?= hermes-run.log
HERMES_LOG_SCRUBBED ?= hermes-run.scrubbed.log
HERMES_LOG_TAIL ?= 60
# `$(call scrubbed_run,<command>)`: run it into $(HERMES_LOG), print only the redactor's
# bounded tail, and keep the command's own exit status (a red run must stay red). The command
# runs in a SUBSHELL: a leg that (accidentally) calls `exit` would otherwise skip the redaction
# and leave the raw stream on the console.
define scrubbed_run
	@rc=0; ( $(1) ) > $(HERMES_LOG) 2>&1 || rc=$$?; \
	python3 scripts/scrub_log.py --in $(HERMES_LOG) --out $(HERMES_LOG_SCRUBBED) --tail $(HERMES_LOG_TAIL) || true; \
	exit $$rc
endef

scrub-log: ## Redact a captured agent log and print its bounded tail (LOG=<path>, OUT=<redacted path>, TAIL=<lines>) — the same redactor every agent leg runs (issue #359)
	@test -n "$(LOG)" || { echo "Usage: make scrub-log LOG=<captured log> [OUT=<redacted path>] [TAIL=60]"; exit 1; }
	python3 scripts/scrub_log.py --in "$(LOG)" $(if $(OUT),--out "$(OUT)",) --tail $(if $(TAIL),$(TAIL),$(HERMES_LOG_TAIL))


AGENT_IMAGE := llgenie/agent:latest
#: The checkout `make agent-repo-ownership` gives back to the invoking user (issue #770).
OWNERSHIP_DIR ?= $(CURDIR)

issue-bot-image: ## Build/pull the agent image the issue-bot runs in (the same image the fix-bot uses; alias of agent-image)
	python3 scripts/ci_images.py ensure agent

issue-bot-triage: ## Hermes REVIEWS the issue (issue.md: body + the whole comment thread + the decision block) and writes its verdict to triage.md (implement | refine | close). No PR, nothing else touched; runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _issue-bot-triage')

_issue-bot-triage: # (internal) the host recipe the agent image runs: the decision, not the code
	hermes -z "Follow the preloaded skill issue-triage. Its Input is issue.md and its Output is triage.md, in the shape the skill prints." -s issue-triage,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

issue-bot-changed: ## Did the implement step actually change the tree? Prints changed=true|false, the bot's own run inputs excluded; exit 2 when git cannot read the tree (issue #428)
	python3 scripts/issue_implementer.py changed
issue-bot-verdict: ## Apply the agent's TRIAGE verdict from triage.md: implement -> nothing (the PR path runs), refine -> ONE comment + agent:refined (no PR), close -> comment with the cited evidence + agent:closed (refused without EVIDENCE)
	@test -n "$(ISSUE)" || { echo "Usage: make issue-bot-verdict ISSUE=<n> [REPO=<owner/repo>]"; exit 1; }
	python3 scripts/issue_implementer.py apply-verdict triage.md --repo $(GH_REPO) --issue $(ISSUE)

# ---- the fast gates run BEFORE the bot pushes (issue #475) -------------------
# The implement leg's agent runs the slow gates while it writes the change, and nothing
# re-checked the FAST ones between "the tree changed" and "the branch is pushed": CI then found
# the bookkeeping reds, and the run that implemented #407 opened six PRs (#443-#448) that were
# functionally green and red only on an unticked `- [ ]` in tasks.md, a stale README target list
# and a wiring count. Each was detectable in seconds here, and each cost a CI round trip plus up
# to an hour of the hourly fix-bot.
#
# ONE list, in `scripts/issue_bot_gates.py`: `FAST_GATES` (what this target runs, in order,
# stopping at the first failure and naming it) and `DEFERRED` (every other gate ci-unit runs, with
# the reason it is not re-checked here). `make test-unit` runs `scripts/issue_bot_gates.py check`,
# which reads THIS file and `.github/workflows/issue-bot.yml` and fails on a ci-unit gate that is
# classified nowhere, a stale classification, a fast gate no `ci-*` job reaches, a target that
# stopped running the script, or a step that is not between the change detection and the push.
issue-bot-gates: ## Run the FAST repository gates in order, stopping at the FIRST failure and naming it (lint, workflows, wiring, docs, PR hygiene, OpenSpec tasks): what the issue-bot runs after the implement step and BEFORE it pushes, so a bookkeeping red never reaches the PR (issue #475)
	python3 scripts/issue_bot_gates.py run

issue-bot-gates-check: ## CI: fail when a ci-unit gate is classified neither fast nor deferred, a fast gate is unwired or not .PHONY, or the issue-bot's gate step is not between the change detection and the push (issue #475)
	python3 scripts/issue_bot_gates.py check

# The JEV preflight (issue #238). The agent image carries the Nerve/JEV decision layer, which
# is what makes a bot run cheaper and more correct: the layer answers "is this the right next
# step" before the model spends a call on it, and the curated context sends the model the part
# of the repo that matters. This target reports whether the layer is available for THIS run and
# puts the provider key where the plugin reads it (run time only — nothing is baked into the
# image, exactly like NOUS_API_KEY).
#
# It NEVER stops a bot: the bots are autonomous, so a missing key or an unreachable provider
# means a normal, slightly more expensive run, reported loudly. `NERVE_REQUIRE=1` turns the
# report into a failure, and EVERY bot workflow sets it: a job whose image has the JEV engine
# turned off does not start, because a bot that silently runs unsupervised is the failure mode
# this guards against. Use NERVE_REQUIRE=1 alone to verify a freshly built image.
bot-sync-main: ## Fetch upstream main and reset the working tree to it, so a NEW branch starts from latest main (issue #303); fails loudly when main cannot be reached
	@bash scripts/bot_sync_main.sh reset

bot-sync-branch: ## Fetch upstream main and rebase the checked-out PR branch onto it before repairing (issue #303); exit 2 means the rebase conflicts and is left to the rebase-bot
	@bash scripts/bot_sync_main.sh rebase

# The AGENT's shell sees every credential this container receives (issue #358).
# Hermes strips provider credentials from its terminal tool, so a key forwarded as
# `-e NOUS_API_KEY` reaches the container and the Hermes process while the agent's
# own shell reads it EMPTY — a bot that then does nothing, green. The plain name and
# the `_HERMES_FORCE_` twin both travel; the probe drives Hermes's REAL terminal
# environment inside the image, so what is asserted is what the agent gets, not what
# `docker run` forwarded. The default list is AGENT_SHELL_KEYS; a job that only
# receives some of them narrows it with AGENT_SHELL_CHECK_KEYS, so the check never
# fails on a key that job legitimately does not have.
AGENT_SHELL_CHECK_KEYS ?= $(AGENT_SHELL_KEYS)
_agent-shell-keys-check: # (internal) the probe, run INSIDE the agent image by the public target
	python3 scripts/agent_shell_keys_check.py $(AGENT_SHELL_CHECK_KEYS)

agent-shell-keys-check: ## Prove every credential a container receives is visible in the AGENT's shell (Hermes strips provider keys from its terminal tool, issue #358); AGENT_SHELL_CHECK_KEYS= narrows it to the keys this job has; the report is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  $(AGENT_SHELL_FORWARD_PLAIN) $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  -e AGENT_SHELL_CHECK_KEYS="$(AGENT_SHELL_CHECK_KEYS)" \
	  $(AGENT_IMAGE) bash -lc 'make _agent-shell-keys-check AGENT_SHELL_CHECK_KEYS="$(AGENT_SHELL_CHECK_KEYS)"')

# ---- the agent's web reach: one masked fetch leg (issue #362) ----------------
# A bot cannot verify what it cannot read. Hermes ships a bundled `browser-firecrawl` plugin keyed
# by FIRECRAWL_API_KEY, so the capability is in the image; what was missing is a sanctioned way to
# use it with the key never printed. ONE leg: the key is read from the ENVIRONMENT inside the
# prompt (never interpolated into it, never echoed), the fetched text is written to a file, and the
# leg's transcript is redacted by #359's seam. A dead key fails the smoke in seconds instead of
# returning an empty result a run reports as success.
agent-fetch: ## Fetch one URL with the masked Firecrawl key and write its text to OUT=path (URL= required; runs INSIDE the agent image)
	@test -n "$(URL)" || { echo "Usage: make agent-fetch URL=<https://…> [OUT=fetched.md]"; exit 1; }
	@python3 scripts/require_env.py NOUS_API_KEY FIRECRAWL_API_KEY
	@python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  $(AGENT_SHELL_FORWARD_PLAIN) $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  -e URL -e OUT \
	  $(AGENT_IMAGE) bash -lc 'make _agent-fetch URL="$$URL" OUT="$$OUT"')

_agent-fetch: # (internal) the host recipe the agent image runs: one fetch, key by name, never printed
	hermes -z "Follow the preloaded skill agent-fetch: the URL is $(URL) and the output file is $(OUT)." -s agent-fetch,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

search-smoke: ## Prove the masked web reach works: one real Firecrawl request with a hard budget, loud on 401/402/403 — never an empty result (BUDGET= chars, default 4000)
	@python3 scripts/require_env.py FIRECRAWL_API_KEY
	@python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  $(AGENT_SHELL_FORWARD_PLAIN) $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  -e BUDGET \
	  $(AGENT_IMAGE) bash -lc 'python3 scripts/fetch_smoke.py --budget "$${BUDGET:-4000}"')

# ---- the reach, DEPLOYED: what a bot run actually depends on (issue #380) ------------------
# #362 built the leg and the smoke; no bot leg called either, so the capability was unreachable from
# a run and nothing said which URLs the bots need. `scripts/web_evidence.py` closes that half:
# `web-coverage` reports each URL's HTTP status (no model, no key — a 404 is dead for a bot too), and
# `issue-evidence` pre-fetches the URLs an issue names with the REAL `agent-fetch` leg, so the agent
# reviews against fetched text instead of guessing. `issue-refiner` is the first consumer.
web-coverage: ## Which URLs a bot run depends on, and do they resolve (a fixture list, or ISSUE_FILE=); non-zero on a dead one — no model call, no key
	python3 scripts/web_evidence.py check $(if $(ISSUE_FILE),$(ISSUE_FILE),tests/fixtures/bot-facing-urls.md) $(if $(URLS),--urls $(URLS),)

issue-evidence: ## Pre-fetch the URLs an issue names so the agent reviews against real text: drives the ONE `agent-fetch` leg, capped, never fatal (ISSUE_FILE=, OUTDIR=fetched, MAX=3)
	@test -n "$(ISSUE_FILE)" || { echo "Usage: make issue-evidence ISSUE_FILE=<path> [OUTDIR=fetched] [MAX=3]"; exit 1; }
	@python3 scripts/web_evidence.py fetch $(ISSUE_FILE) --outdir $(if $(OUTDIR),$(OUTDIR),fetched) --max $(if $(MAX),$(MAX),3)

agent-jev-preflight: ## Prove the JEV engine is active in the agent image; every bot workflow runs it with NERVE_REQUIRE=1, so a job whose engine is off does not start. NERVE_GATE_SKIP_PROVIDER=1 skips the live provider call; the report is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py TYPESAFE_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE -e NERVE_GATE_SKIP_PROVIDER \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _agent-jev-preflight')
# The JEV preflight as a bot STEP depends on it (issue #802). `agent-jev-preflight NERVE_REQUIRE=1`
# is a bot job's first step, and when the engine is off the step failed with a step name only: an
# operator could not tell a missing provider secret from a broken image, and (measured 2026-10-28,
# issue-dedupe runs 40697636784 and 40702295009) nothing tracked it, so a duplicate sweep that
# decided nothing looked exactly like a sweep with nothing to do. This target keeps that exit status
# (the step stays red) and adds what the run owed the reader: the failure CLASS and its fix in the
# output, and ONE tracker issue per class (`scripts/jev_preflight_tracker.py`, marker-deduped) — a
# second run of the same class prints the existing issue and files nothing.
jev-preflight-required: ## Run the JEV preflight as a bot step does: on failure print the failure class + its fix and file ONE deduped tracker (REPO=; RUN_URL=; DRY=1 previews). Never softens the exit status (issue #802)
	@test -n "$(REPO)" || { echo "Usage: make jev-preflight-required REPO=<owner/repo> [RUN_URL=<url>] [DRY=1]"; exit 1; }
	@log=$$(mktemp); \
	$(MAKE) --no-print-directory agent-jev-preflight NERVE_REQUIRE=1 >"$$log" 2>&1; rc=$$?; \
	cat "$$log"; \
	if [ $$rc -eq 0 ]; then rm -f "$$log"; exit 0; fi; \
	python3 scripts/jev_preflight_tracker.py report --repo "$(GH_REPO)" --log "$$log" \
	  $(if $(RUN_URL),--run-url "$(RUN_URL)",) $(if $(DRY),--dry,) \
	  $(if $(filter true,$(GITHUB_ACTIONS)),,--local) || true; \
	rm -f "$$log"; \
	echo "::error::the JEV decision layer is inactive, so this bot step did not start — the failure class and its fix are above, and $(GH_REPO) carries the tracker (issue #802)"; \
	exit $$rc
# The code-review bot (issue #269): it reads the TREE and the PIPELINES and files what is
# actually wrong. Its whole output is issues — analysis, never implementation (AGENTS.md,
# #231) — so it never edits a file, never opens a PR and never merges; each issue carries the
# evidence the finding was derived from, so a reviewer can check the claim without re-deriving
# it. `scan` is free (no model, no API writes); `file` writes issues and dedups by a marker in
# the body, so a re-run of an unchanged tree files nothing.
code-review-scan: ## The code-review bot's checks: tree + pipelines -> findings (REPO=; STATIC=1 skips the checks that read the GitHub API; JSON=1 for machine output; no model spend, writes nothing)
	python3 scripts/code_review.py scan --repo "$(GH_REPO)" $(if $(STATIC),--static-only,) $(if $(JSON),--json,)
code-review-file: ## File ONE issue per NEW code-review finding, capped per run (REPO=; CAP= issues per run, default 3; DRY=1 previews) — never edits code, never merges
	@test -n "$(REPO)" || { echo "Usage: make code-review-file REPO=<owner/repo> [CAP=3] [DRY=1]"; exit 1; }
	python3 scripts/code_review.py file --repo "$(GH_REPO)" $(if $(CAP),--cap $(CAP),) $(if $(DRY),--dry,)

# ---- the architecture bot (issue #449) ---------------------------------------
# `docs/ARCHITECTURE.md` is the map of the shipped path, and it ages the moment the tree moves.
# This bot re-derives it every 6 hours: a deterministic brief from real `git` state (no model),
# ONE Hermes leg that may write only that doc, and a deterministic publish that files ONE issue
# and ONE linked PR. A run with no drift files nothing, and no run ever merges.
DOC ?= docs/ARCHITECTURE.md
ARCH_BRIEF ?= architecture-brief.md
STAMP ?= $(shell date -u +%Y%m%dT%H%M)

architecture-bot-brief: ## Derive the architecture doc's brief from the real tree and the drift since the doc's last commit (DOC= path, OUT= path; no model, writes only the brief — issue #449)
	python3 scripts/architecture_bot.py brief --doc "$(DOC)" --out "$(ARCH_BRIEF)"

architecture-bot-doc: ## Rewrite the architecture doc with Hermes INSIDE the agent image from the brief (DOC=; the doc is the ONLY writable file); the transcript is REDACTED (issue #449)
	@python3 scripts/require_env.py NOUS_API_KEY
	@test -f "$(ARCH_BRIEF)" || { echo "Run 'make architecture-bot-brief' first: $(ARCH_BRIEF) is missing"; exit 1; }
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _architecture-bot-doc DOC="$(DOC)" ARCH_BRIEF="$(ARCH_BRIEF)"')

_architecture-bot-doc: # (internal) the host recipe the agent image runs: only the doc is writable
	$(MAKE) _agent-jev-preflight
	hermes -z "Follow the preloaded skill architecture-doc. The brief is $(ARCH_BRIEF); the only file you may write is $(DOC)." -s architecture-doc,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

architecture-bot-publish: ## File ONE issue + ONE linked PR for the doc change (REPO=; DOC=; STAMP=; DRY=1 previews) — nothing without drift, never merges (issue #449)
	@test -n "$(REPO)" || { echo "Usage: make architecture-bot-publish REPO=<owner/repo> [DOC=docs/ARCHITECTURE.md] [DRY=1]"; exit 1; }
	python3 scripts/architecture_bot.py publish --repo "$(GH_REPO)" --doc "$(DOC)" --stamp "$(STAMP)" $(if $(DRY),--dry,)

architecture-bot: ## Run the architecture bot locally end to end: brief -> doc -> issue + PR (needs NOUS_API_KEY and REPO=; DRY=1 stops at the preview)
	@$(MAKE) architecture-bot-brief DOC="$(DOC)"
	@$(MAKE) architecture-bot-doc DOC="$(DOC)"
	@$(MAKE) architecture-bot-publish REPO="$(REPO)" DOC="$(DOC)" $(if $(DRY),DRY=1,)

# The run-failure reactor (issue #286): a bot that reacts to a FAILED CI run — any run, not just
# a PR check — and routes it to a remedy. The route decision lives in scripts/run_failure_reactor.py
# (stdlib only, no LLM), never in a job `if:` that can silently skip (issue #107). Route A: a
# pushable same-repo PR -> claim it (scripts/bot_claims.py, #279/#285) and dispatch the EXISTING
# fix-bot. Route B: no pushable PR -> file ONE marker-deduped issue labelled `agent:implement`.
# It never repairs/commits/pushes/merges in the file-issue path; a run it cannot diagnose is loud.
# The identity `gh workflow run` dispatches with (issue #555): the dispatched run's actor IS the
# token's identity, and every guarded workflow here refuses `github-actions[bot]` (#510), so a
# dispatch made with the job token produced a fix-bot run that died in its own guard (run
# 39917926028). The owner PAT is passed by NAME in the environment only — never on argv, never in a
# log. Locally it defaults to whatever GH_TOKEN the shell already holds.
DISPATCH_TOKEN ?= $(GH_TOKEN)
export DISPATCH_TOKEN

run-failure-reactor: ## Route a failed CI run to a remedy (issue #286): a PR this bot can push (this repo, or the owner's fork) -> dispatch the fix-bot as the OWNER (DISPATCH_TOKEN); else file ONE deduped issue labelled agent:implement (REPO=; RUN_ID=; DRY=1 previews)
	@test -n "$(REPO)" || { echo "Usage: make run-failure-reactor REPO=<owner/repo> RUN_ID=<run> [DRY=1]"; exit 1; }
	@test -n "$(RUN_ID)" || { echo "Usage: make run-failure-reactor REPO=<owner/repo> RUN_ID=<run> [DRY=1]"; exit 1; }
	python3 scripts/run_failure_reactor.py --repo "$(GH_REPO)" --run-id "$(RUN_ID)" $(if $(DRY),--dry,)

implement-issue: ## Implement issue.md with Hermes INSIDE the agent image (AGENTS.md is the authority; NOUS_API_KEY/GH_TOKEN from secrets; runs the gates; pushes nothing); the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e GH_TOKEN -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _implement-issue')
	$(MAKE) --no-print-directory agent-repo-ownership
	$(MAKE) --no-print-directory issue-bot-pr-body-check ISSUE=$(if $(ISSUE),$(ISSUE),$(shell echo "$(BRANCH)" | sed -n 's|^agent/issue-\([0-9]*\).*|\1|p'))

agent-repo-ownership: ## Give the mounted checkout back to the invoking user after a containerized agent leg (a root-run leg leaves `.git/objects` unwritable, so the next `git add` dies with "insufficient permission"; issue #770)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm -v "$(OWNERSHIP_DIR):/repo" --entrypoint chown \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) -R $(shell id -u):$(shell id -g) /repo)

issue-bot-pr-body-check: ## CI: refuse the agent's pr-body.md before the leg spends its gates on a body that cannot become a PR (a missing or empty Issue:/Fix:/Benefit:/Technical: part; issue #770)
	@test -f $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) || { echo "[issue-implementer] no $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) was written - the leg cannot open a PR without it (issue #770)"; exit 1; }
	python3 scripts/issue_implementer.py check-body --body-file $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) $(if $(ISSUE),--issue $(ISSUE),)

hermes-smoke: ## Prove the alias the bots use can CALL A TOOL, inside the agent image: a terminal call that prints a per-run nonce, asserted from the session transcript (die in seconds, not after 20 min); the transcript is REDACTED before it prints (issues #359, #407)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo -e NOUS_API_KEY \
	  -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _hermes-smoke')

# Inside the image: the JEV preflight first, so the run knows whether the decision layer is
# there. It reports; it never blocks.
_agent-jev-preflight: # (internal) report whether the JEV layer is available in this home.
# Invoked inside the agent image by the public `agent-jev-preflight` target, and by
# `_implement-issue` before any agent work.
	/usr/local/bin/agent_jev_preflight.sh

_implement-issue: # (internal) the host recipe: implement issue.md with Hermes. Invoked
# inside the agent image by the public `implement-issue` target.
	$(MAKE) _agent-jev-preflight
	hermes -z "Follow the preloaded skill issue-implement. Its Input is issue.md; leave the change uncommitted in /repo and write pr-body.md at the repo root." -s issue-implement,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
_hermes-smoke: # (internal) one real Hermes call that MUST use its terminal tool. Invoked inside
# the agent image by the public `hermes-smoke` target.
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/hermes_smoke.py run --alias $(nous-model) --reasoning low
nerve-profile-check: ## Probe the rule the agent image build enforces: a nerve setting whose module the selected profile does not register is inert, so the build fails (issue #611)
	python3 scripts/nerve_profile_check.py --self-test

sync-strata-models: ## Write data/strata_models.json from Strata's setup.py at the skill's pinned commit (the GGUF files Strata runs)
	python3 scripts/strata_models.py sync
check-strata-models: ## CI: fail when data/strata_models.json differs from Strata's setup.py at the pinned commit
	python3 scripts/strata_models.py check
engine-bump-rebase: ## Rebase every open chore/engine-bump-* PR onto the latest main (DRY=1 prints what it would do and pushes nothing)
	python3 scripts/engine_bump_rebase.py $(if $(DRY),--dry,)
check-dispatch-forms: ## CI: fail when a dispatchable workflow does not state the work it will do: name, documented dispatch inputs, header block, and the docs/BOTS.md table
	python3 scripts/check_dispatch_forms.py check
dispatch-forms-report: ## Print the dispatch table in docs/BOTS.md (generated from the workflow files; paste it between the dispatch-forms markers)
	python3 scripts/check_dispatch_forms.py report
issue-cleaner-scan: ## Which OPEN issue a merged PR already implemented (the linkage guard cannot see, issue #325): prints each finding and its evidence, closes nothing (REPO= picks the repo)
	python3 scripts/issue_cleaner.py --repo "$(GH_REPO)" --dry
issue-cleaner-apply: ## Close the issues a merged PR implemented but left open, each with a comment citing the PR and its merge commit (issue #325; REPO= picks the repo)
	python3 scripts/issue_cleaner.py --repo "$(GH_REPO)"
worktree-report: ## Report every worktree with its branch, merged-into-main, open PR and dirty state; mutates nothing and deletes nothing (issue #794); SLUG= picks the repo gh reads, BASE= the base ref
	python3 scripts/worktree_report.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main)
worktree-prune: ## Remove the worktrees and local branches whose PR already merged, proven by the PR's merge commit (squash merges defeat ancestry, issue #431); DRY=1 prints the plan, BASE= picks the base ref, SLUG= the owner/name gh reads; an UNATTENDED run — CI, BOT, or the dispatcher's HERMES_KANBAN_* — is REFUSED unless CONFIRM=1 (issue #794)
	@python3 scripts/worktree_prune_guard.py
	python3 scripts/worktree_prune.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main) $(if $(DRY),--dry,)
queued-alarm: ## Report jobs stuck in `queued` far too long (a runner that never picks them up, issue #254); COMMENT=1 delivers the report, DRY=1 previews it
	python3 scripts/queued_run_alarm.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(COMMENT),--comment,) $(if $(DRY),--dry,)
sweep-concurrency-report: ## Report every scheduled workflow whose runs stack instead of superseding, with the measurement and the decision each one needs (issue #917)
	python3 scripts/sweep_concurrency.py report
ci-requeue-cancelled: ## Re-run the CI runs a bulk cancel killed, ONLY where the head sha has no other run (WINDOW=2h, DRY=1 previews; issue #843)
	python3 scripts/ci_requeue.py run --repo $(GH_REPO) --window $(if $(WINDOW),$(WINDOW),2h) $(if $(DRY),--dry,)

fix-loop-image: ## Run the fix-bot loop inside the agent image (the same image the workflow uses); AGENT_IMAGE overrides the resolved ref, LOG=path also receives the REDACTED log (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	$(call scrubbed_run,img=$$(if [ -n "$(AGENT_IMAGE)" ]; then echo "$(AGENT_IMAGE)"; else python3 scripts/ci_images.py latest agent; fi); echo "agent image: $$img"; $(RUNTIME) run --rm --init -v "$$PWD:/repo" -w /repo -e NOUS_API_KEY -e GH_TOKEN -e FIX_CHECK -e FIX_ROUNDS -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) "$$img" bash -lc 'scripts/agent_jev_preflight.sh && FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh'; $(if $(LOG),cp -f $(HERMES_LOG_SCRUBBED) $(LOG),true))

fix-bot-sweep: ## Which red PR the fix-bot should repair, and dispatch it (DRY=1 previews; needs gh)
	python3 scripts/fix_bot_sweep.py --repo $(GH_REPO) --check "$(if $(CHECK),$(CHECK),make ci-unit)" --max-attempts $(if $(ATTEMPTS),$(ATTEMPTS),5) $(if $(OWN_FORK),--own-fork $(OWN_FORK),) $(if $(PR),--pr $(PR),) $(if $(REPORT_FILE),--report-file "$(REPORT_FILE)",)$(if $(DRY),--dry,)

fix-bot-report: ## Render the fix-bot's failure report from the loop's report file (REPORT=<path>; the same command the workflow uses to comment)
	python3 scripts/fix_bot_report.py "$(if $(REPORT),$(REPORT),/tmp/fix-report.txt)" --command "$(if $(CHECK),$(CHECK),make ci-unit)"

agent-image-ref: ## Print the GHCR :latest ref every agent pull uses (publish points it at the content hash)
	@python3 scripts/ci_images.py latest agent

fix-loop: ## Run the PR fix-bot loop locally against the failing check (scripts/fix_loop.sh; needs an agent on PATH)
	FIX_ROUNDS="$(if $(ROUNDS),$(ROUNDS),5)" FIX_CHECK="$(if $(CHECK),$(CHECK),make ci-unit)" FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh

check-secret-output: ## CI: fail when any file prints a secret's VALUE, passes it on a command line, xtraces it, dumps the environment around it, or commits a credential-shaped literal
	python3 scripts/check_secret_output.py check
secret-output-report: ## Show which files name a secret-shaped variable, and whether any prints it
	python3 scripts/check_secret_output.py report

# ---- secret scan: no credential VALUE may reach the repo (issue #360) -------
# `check-secret-output` reads the SHAPES a script prints; this reads the VALUE a
# human or a bot committed, which a shape rule cannot see (a PAT, a JWT, an
# AWS-style key, a bearer inside a URL). gitleaks runs in ITS OWN pinned image:
# the test image has no docker inside, so the scanner cannot live in it.
# `--redact` keeps the finding out of the log, and `.gitleaks.toml` allowlists only
# documented PLACEHOLDERS — a real value is removed and rotated, never allowlisted.
GITLEAKS_IMAGE := ghcr.io/gitleaks/gitleaks:v8.30.1
GITLEAKS_RUN := $(RUNTIME) run --rm -v "$$PWD":/repo -w /repo $(GITLEAKS_IMAGE)

# The working-tree scan reads the COMMITTABLE set, not the whole filesystem (issue #382): `gitleaks
# dir` honours no .gitignore, so pointing it at the checkout reported findings inside
# `tests/__pycache__/*.pyc` — gitignored bytecode carrying the suites' own sentinels — and printed the
# "rotate the key" remediation for files nobody can commit. `scripts/secret_scan.py` exports
# `git ls-files -c -o --exclude-standard` (what `git add` would take) and runs the same pinned image
# and config against that tree.
_secret-scan: # (internal) the working-tree scan over the committable set; `secret-scan` wraps it with the remediation text
	python3 scripts/secret_scan.py --runtime $(RUNTIME)

secret-scan: ## CI: fail when a credential VALUE is committed in the working tree (gitleaks, its own pinned image; a finding means remove it and rotate the key — never allowlist it)
	@python3 scripts/secret_scan.py --runtime $(RUNTIME); rc=$$?; \
	if [ $$rc -eq 1 ]; then \
		echo "SECRET SCAN FAILED: a credential shape is present in the working tree."; \
		echo "Remove the value, rotate the key in the provider AND in the GitHub secret, and only"; \
		echo "then push. Never add it to .gitleaks.toml to make the scan pass — an allowlist is"; \
		echo "for a documented PLACEHOLDER, never for a real value."; \
		exit 1; \
	elif [ $$rc -ne 0 ]; then \
		echo "SECRET SCAN COULD NOT RUN (exit $$rc): the scanner produced NO verdict. This is not a"; \
		echo "clean tree and not a finding — read the message above and fix the scan itself. Never"; \
		echo "report a scan that could not run as clean (issue #382)."; \
		exit $$rc; \
	fi

_secret-scan-history: # (internal) the history scan; refuses a worktree, where .git is a file
	@if [ -f .git ]; then \
		echo "SECRET SCAN (history) needs a real clone: this checkout is a git worktree (.git is a file)."; \
		echo "Run it in the primary checkout or in CI."; \
		exit 1; \
	fi
	$(GITLEAKS_RUN) git /repo --config /repo/.gitleaks.toml --redact --no-banner --exit-code 1

secret-scan-history: ## Fail when a credential VALUE is anywhere in the git history — host-only by design: it refuses a worktree and CI clones shallowly, so run it in a real clone before a release
	@$(MAKE) --no-print-directory _secret-scan-history

secret-scan-self-test: ## CI: prove the scanner is not a false green — a planted fake credential MUST be caught, and the same tree is clean once it is removed
	python3 scripts/secret_scan_self_test.py
check-wiring: ## CI: fail when a test/script is wired to no make target or only to one CI never runs, when a recorded host-only exception is stale, when a workflow calls a make target that does not exist, or when a `.PHONY` entry names no target or a target that runs nothing (issue #883)
	python3 scripts/check_wiring.py check
wiring-report: ## Show how every test/script is wired (which make target, and whether CI runs it) and the recorded host-only exceptions
	python3 scripts/check_wiring.py report
check-docs: ## CI: fail when a user-facing (## help) make target is undocumented, a recorded exception is stale, an agent-wiki/ note references no issue or has no index row in docs/changes.d/, or README.md carries change history (issues #257, #678, #934)
	python3 scripts/changes_index.py check
	python3 scripts/check_docs.py check
docs-report: ## Show every user-facing make target as documented / missing / a recorded exception, and each agent-wiki/ note's issue references + its docs/changes.d/ index row
	python3 scripts/check_docs.py report
changes-index: ## Render CHANGES.md from the one-row-per-change files in docs/changes.d/ (never edit CHANGES.md by hand; one row per file is what keeps two open PRs from conflicting — issue #934)
	python3 scripts/changes_index.py write
changes-index-report: ## Show the docs/changes.d/ fragment census and how many rows CHANGES.md is behind them
	python3 scripts/changes_index.py report
auto-merge: ## Merge a PR ONLY when this run is green and the PR is conflict-free: state OPEN, mergeable MERGEABLE, mergeStateStatus CLEAN (no conflicts, not behind, not blocked), head pinned to HEAD_SHA, no do-not-merge label; then verify what it closed (PR= REPO= HEAD_SHA= from ci.yml; APPROVE=1 approves a green review-blocked PR with the other allowed identity; DRY=1 prints the decision)
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make auto-merge PR=<n> REPO=<owner/repo> [HEAD_SHA=<sha>] [APPROVE=1] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py auto-merge --repo "$(GH_REPO)" --pr $(PR) $(if $(HEAD_SHA),--head-sha $(HEAD_SHA),) $(if $(APPROVE),--approve-when-review-required,) $(if $(ACTOR),--actor $(ACTOR),) $(if $(DRY),--dry,)
# The auto-merge workflow is a `workflow_run`, so GitHub hands it a RUN ID, not a PR number: the run has
# to be resolved back to its PR before anything can be merged (issue #508). A fork `pull_request` run
# 404s on the runs endpoint and `gh api` prints the error BODY to stdout, so a value counts as a PR
# number only when it is digits; anything else falls through to the head-branch search, and nothing
# resolving fails loudly. The logic lives in scripts/resolve_run_pr.py and is tested in
# tests/test_resolve_run_pr.py — this target is the one code path the workflow runs.
auto-merge-resolve: ## Resolve the open PR a finished CI run belongs to (REPO= RUN_ID= HEAD_OWNER= HEAD_BRANCH=): writes `number=<n>` to $GITHUB_OUTPUT, treats a 404/error body as no answer and falls back to the fork head search, and fails loudly when nothing resolves (issue #508)
	@test -n "$(REPO)" && test -n "$(RUN_ID)" && test -n "$(HEAD_OWNER)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make auto-merge-resolve REPO=<owner/repo> RUN_ID=<id> HEAD_OWNER=<owner> HEAD_BRANCH=<branch>"; exit 1; }
	python3 scripts/resolve_run_pr.py resolve --repo "$(GH_REPO)" --run-id $(RUN_ID) --head-owner "$(HEAD_OWNER)" --head-branch "$(HEAD_BRANCH)"

# The fix-bot's sweep asks the SAME question with the opposite consequence (issue #629): a `CI` failure
# report can arrive after its PR already merged or closed, and then there is nothing to repair — so an
# empty answer is an answer (exit 0, `number=`), never a red run. The merge gate above must keep failing
# loudly, which is why this is a separate target over one resolver rather than a shared default.
fix-bot-resolve: ## Resolve the open PR a failed CI run belongs to for the fix-bot sweep (REPO= RUN_ID= HEAD_OWNER= HEAD_BRANCH=): writes `number=<n>` to $GITHUB_OUTPUT, and answers an EMPTY `number=` with exit 0 when the PR already merged or closed — nothing to repair, not a failure (issue #629)
	@test -n "$(REPO)" && test -n "$(RUN_ID)" && test -n "$(HEAD_OWNER)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make fix-bot-resolve REPO=<owner/repo> RUN_ID=<id> HEAD_OWNER=<owner> HEAD_BRANCH=<branch>"; exit 1; }
	python3 scripts/resolve_run_pr.py resolve --repo "$(GH_REPO)" --run-id $(RUN_ID) --head-owner "$(HEAD_OWNER)" --head-branch "$(HEAD_BRANCH)" --allow-none

auto-merge-recheck: ## Re-evaluate the open PRs whose own deferral marker matches their current head — a deferral is retried without a push (REPO= [MAX=5] [DRY=1]) (issue #545)
	@test -n "$(REPO)" || { echo "Usage: make auto-merge-recheck REPO=<owner/repo> [MAX=5] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py recheck --repo "$(GH_REPO)" --max-prs $(if $(MAX),$(MAX),5) $(if $(DRY),--dry,)

auto-merge-explain: ## Print why a PR was (or was not) auto-merged: state, mergeability, merge state, review decision, author and the verdict — writes NOTHING (PR= REPO= [HEAD_SHA=])
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make auto-merge-explain PR=<n> REPO=<owner/repo> [HEAD_SHA=<sha>]"; exit 1; }
	python3 scripts/auto_merge.py explain --repo "$(GH_REPO)" --pr $(PR) $(if $(HEAD_SHA),--head-sha $(HEAD_SHA),)
verify-closure: ## Prove a merged PR closed what its body claims: prints every closing reference and its state, and fails naming an issue that is still OPEN (PR= REPO=)
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make verify-closure PR=<n> REPO=<owner/repo>"; exit 1; }
	python3 scripts/verify_closure.py verify --repo "$(GH_REPO)" --pr $(PR)
check-holds: ## CI: fail when an open PR carries `do-not-merge` with no resolving issue named anywhere (issue #948)
	python3 scripts/check_holds.py check

holds-report: ## Print every open PR carrying `do-not-merge` and the issue it names as the remedy (issue #948)
	python3 scripts/check_holds.py report

.PHONY: check-holds holds-report

check-pr-hygiene: ## CI: fail when a producer's commit message or PR body is empty, a placeholder, a subject with no body, or when AGENTS.md lost the mandate (issue #313)
	python3 scripts/check_pr_hygiene.py check
pr-hygiene-report: ## Show every producer the PR/commit-message guard reads, and its verdict
	python3 scripts/check_pr_hygiene.py report

check-pr-heads: ## Warn (never fail) when an open PR's head lives in another repository, naming it with the reason and the remedy (issue #910)
	python3 scripts/pr_heads.py check
pr-heads-report: ## Show every open PR grouped by head repository, with the same-repo rule and why it is the rule (issue #910)
	python3 scripts/pr_heads.py report
arm-auto-merge: ## Arm auto-merge on every open PR that is not a draft and not already armed (AUTHOR= limits it to one lane; DRY=1 calls nothing — issue #912)
	python3 scripts/arm_auto_merge.py arm $(if $(AUTHOR),--author "$(AUTHOR)",) $(if $(DRY),--dry,)
arm-auto-merge-report: ## Show the open PRs that carry no auto-merge intent yet, with their author and mergeable state (issue #912)
	python3 scripts/arm_auto_merge.py report $(if $(AUTHOR),--author "$(AUTHOR)",)
check-issue-bodies: ## CI: fail when a producer hand-builds an issue body, a body misses a section or puts `## Technical` anywhere but last, an acceptance criterion is absent, or AGENTS.md / the issue skills lost the rule (issue #745)
	python3 scripts/check_issue_body.py check
issue-bodies-report: ## Show every issue producer, whether it renders through the one seam, the section order and the verdict
	python3 scripts/check_issue_body.py report
# BASE/HEAD bound the commit range the guard reads (defaults: origin/main..HEAD). ci-unit runs it with
# no range, so the static half (AGENTS.md + the producers) is still checked on a push to main; a PR
# run reads the commits the PR adds.
PR_BASE ?= origin/main
MODE ?= full
PR_HEAD ?= HEAD
check-pr-authors: ## CI: fail when a PR's commit is authored through an allowlisted email address, when a Co-authored-by trailer names anyone else, or when a producer commits off the allowlist (issue #345)
	python3 scripts/check_pr_authors.py check --base "$(PR_BASE)" --head "$(PR_HEAD)"
pr-authors-report: ## Show every commit in the range with its author verdict, and the identity each producer assigns
	python3 scripts/check_pr_authors.py report --base "$(PR_BASE)" --head "$(PR_HEAD)"
# The ONE source of the identity every leg commits as (issue #840). `git-identity-apply` writes the
# allowlisted pair into THIS repository's git config — the one place a leg sources it from, instead of
# nine literals in three spellings, or whatever the host's ~/.gitconfig happens to hold.
# `check-git-identity` fails when the identity git would actually use is outside
# `scripts/check_pr_authors.py::ALLOWED`, naming where it came from (GIT_AUTHOR_EMAIL, a config file).
# `git-identity-line` is the `Author:` line a bot's PR body carries. All three are CI/leg plumbing, so
# none carries a `##` help line: `make help` documents what a USER runs.
git-identity-apply:
	python3 scripts/git_identity.py apply
check-git-identity:
	python3 scripts/git_identity.py check
git-identity-line:
	@python3 scripts/git_identity.py line
git-identity-report:
	python3 scripts/git_identity.py report
check-workflows: ## CI: fail when a YAML file's GitHub expression does not parse, when a YAML file lacks a trailing newline, when a workflow has no top-level name, or when a `workflow_run` roster names a workflow that does not exist or leaves one unwatched (issues #330, #349)
	python3 scripts/check_workflows.py check
workflows-report: ## Show every YAML file the workflow gate reads, how many expressions it validated, and its verdict
	python3 scripts/check_workflows.py report
check-module-names: ## CI: fail when a LIVE file spells the retired CLI module name instead of scripts/llgenie_serve.py (the old spelling belongs to the deprecated shim and the dated history only; issues #251, #573, #812)
	python3 scripts/module_name_guard.py check
sbom: ## Generate the CycloneDX SBOM with the pinned Syft image into security-reports/sbom.cdx.json (issue #715)
	python3 scripts/security_scan.py sbom
security-scan: ## Run ONE scanner from its immutable image (TOOL=syft|trivy|grype|semgrep); grype needs the Syft SBOM first (issue #715)
	python3 scripts/security_scan.py scan "$(TOOL)"
security-scan-all: ## Run every scanner from its pinned image in dependency order (Syft SBOM, then Trivy, Grype, Semgrep)
	python3 scripts/security_scan.py all
security-verdict: ## Apply data/security-policy.json to the reports (EVENT=<github event> decides whether that event may gate; ENFORCE=pr forces report-only; issue #715, #738)
	python3 scripts/security_scan.py verdict --event "$(EVENT)" $(if $(ENFORCE),--mode "$(ENFORCE)",)
check-security-scan: ## CI: fail when the scan policy is empty/unknown or a scanner ref is missing from digests.json (issue #715)
	python3 scripts/security_scan.py check
security-issues-plan: ## Print the tagged issues the current reports would create/update/clear and mutate nothing (issue #716)
	python3 scripts/security_issues.py plan
security-issues: ## File or update the tagged vulnerability issues for the current reports (SLUG=owner/name, RUN_URL=<run link>, issue #716)
	python3 scripts/security_issues.py apply --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" --run-url "$(RUN_URL)"
check-security-issues: ## CI: fail when the issue policy/label roster/marker disagree (issue_severities not a subset of fail_on, a missing label, a marker that does not round-trip) (issue #716)
	python3 scripts/security_issues.py check
security-bot-pick: ## Print the ONE auto-fixable issue the remediation bot would take, and what it would edit (issue #717)
	python3 scripts/security_bot.py select --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)"
security-bot: ## Apply the advisory's pin, run the fast gates, and open ONE PR that closes the issue (DRY=1 prints the edit and pushes nothing; issue #717)
	python3 scripts/security_bot.py apply --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" $(if $(DRY),--dry,)
check-security-bot: ## CI: fail when the bot's select labels/pin sources disagree with the issue roster or a compiled requirements file became an edit target (issue #717)
	python3 scripts/security_bot.py check
security-bumps-plan: ## Print the minimum version the scan's findings demand per package, the pins it would move, and the issues the bump PR would close (issue #738)
	python3 scripts/security_bumps.py plan
security-bumps: ## Write tools/security-floors.in, regenerate the compiled pins through the one generator, and open ONE PR that closes the issues it fixes (DRY=1 prints and pushes nothing; issue #738)
	python3 scripts/security_bumps.py apply --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" $(if $(DRY),--dry,)
check-security-bumps: ## CI: fail when a floor line states no advisory, a compiled pin is below its floor, or the `-c security-floors.in` include is gone (issue #738)
	python3 scripts/security_bumps.py check
scanner-image: ## Build one scanner image from containers/scanners/<SCANNER>/Dockerfile (SCANNER=trivy|grype|semgrep, issue #714)
	python3 scripts/scanner_image.py build "$(SCANNER)"
test-scanner-image: ## Build a scanner image and prove it prints the version its Dockerfile pins (SCANNER=<id>)
	python3 scripts/scanner_image.py test "$(SCANNER)"
scanner-digests: ## Rewrite containers/scanners/digests.json from the Dockerfiles (the immutable tag + pinned version per scanner)
	python3 scripts/scanner_image.py write
scanner-ref: ## Print the published immutable ref of a scanner image (SCANNER=<id>)
	python3 scripts/scanner_image.py ref "$(SCANNER)"
publish-scanner-images: ## Build linux/amd64+arm64 and push one scanner image's content-hash tag to GHCR (SCANNER=<id>; the scanner-images job publishes through make ci-scanner-images)
	python3 scripts/scanner_image.py publish "$(SCANNER)"
ci-scanner-images: ## CI job scanner-images: build and version-test every scanner image, publish on a push run only (policy in the script)
	python3 scripts/scanner_image.py ci
check-scanner-images: ## CI: fail when a scanner Dockerfile floats (tag base, version range) or digests.json is stale (issue #714)
	python3 scripts/scanner_image.py check all
check-actions: ## CI: fail when a GitHub Action in any workflow or composite action is not pinned to a full commit SHA (issue #719)
	python3 scripts/pin_actions.py check
actions-report: ## Show every `uses:` ref the action-pin gate reads, its pin state and its tag
	python3 scripts/pin_actions.py report
update-actions: ## Re-resolve every pinned action's tag to its current commit SHA and rewrite the workflows (needs gh + network)
	python3 scripts/pin_actions.py update
check-renovate: ## CI: fail when renovate.json automerges more than low-risk updates, opens a second merge path, or may edit a generated/vendored file (issue #718)
	python3 scripts/check_renovate.py check
renovate-report: ## Show every Renovate package rule, its managers, its automerge state and the ignored paths
	python3 scripts/check_renovate.py report
# UNSUPPORTED=<file>: upstream engines with no skill are omitted from the trend
# offer (no image). Passing the decisions file tolerates ONLY the engines recorded
# there with a dated decision (issue #229); an engine with no skill and no decision
# is "new and unresolved" and FAILS, naming it. Without --unsupported every
# registry engine with no skill is an error, so the pinned fixture stays strict.
UNSUPPORTED ?=
# ALLOW_NEW_ENGINES=1 is the DATA-CARRYING scope (issue #683): the weekly registry-sync must be
# able to land a store that first names an engine llgenie does not ship — its next step opens
# that engine's tracking issue, and ci-unit's check-engine-skill-gap is the gate that keeps the
# PR red until the engine ships or gets a dated decision. Never pass it from ci-unit.
skills-validate: ## Validate every engine skill against the trending-local-llms registry (ALLOW_NEW_ENGINES=1: carry a new unshipped engine, for the registry-sync job only)
	python3 scripts/engine_skills.py validate --registry "$(REGISTRY)" $(if $(UNSUPPORTED),--unsupported "$(UNSUPPORTED)",) $(if $(ALLOW_NEW_ENGINES),--allow-new-engines,)
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
generate-engine-params: ## Regenerate containers/engines/params/*.json + binaries.json (binary file + documented flags per image) from the current engine skills (per engine x arch; ENGINE=<id> writes only that engine)
	python3 scripts/engine_skills.py params $(if $(ENGINE),--only $(ENGINE),)
check-engine-params: ## CI: fail if committed engine params or the binaries manifest differ from what the skills generate
	python3 scripts/engine_skills.py params --check
check-engine-coverage: ## CI: fail if a shipped servable engine has no buildable CI image cell (disabled, no linux, no params) and no recorded exception
	python3 scripts/engine_coverage.py check
engine-coverage-report: ## Print every shipped engine and whether CI builds it, is deliberately not an image, or is an unbuilt exception (issue #771)
	python3 scripts/engine_coverage.py report
check-engine-source: ## CI: fail if a cell claims a source build (prebuilt=false) but its install steps only download a wheel/archive
	python3 scripts/engine_source_guard.py check
engine-source-report: ## Print the source-vs-prebuilt census of every engine x arch cell, and every tracked exception
	python3 scripts/engine_source_guard.py report
check-engine-launchers: ## CI: fail when a ~/bin/llgenie-engine-* launcher names a different image tag than the committed params compute (a stale launcher silently runs an older pinned engine; issue #842; CHECK_REGISTRY=1 also fails a tag no manifest resolves)
	python3 scripts/check_engine_launchers.py check $(if $(BIN),--bin "$(BIN)",) $(if $(ARCH),--arch "$(ARCH)",) $(if $(CHECK_REGISTRY),--check-registry,)
engine-launchers-report: ## Print, per engine, the image tag this host's launcher carries next to the one the committed params compute (issue #842)
	python3 scripts/check_engine_launchers.py report $(if $(BIN),--bin "$(BIN)",) $(if $(ARCH),--arch "$(ARCH)",)
check-model-links: ## CI: prove every committed model/GGUF link a test depends on resolves (static, no network; LIVE=1 probes the real Hub via tests/hub_probe — the ONE liveness authority, issue #1000; LIMIT bounds a live sweep)
	python3 scripts/check_model_links_liveness.py check $(if $(LIVE),--live,) $(if $(LIMIT),--limit $(LIMIT),)
model-links-report: ## Print every committed model/GGUF link the tests depend on, with its caller (issue #1000)
	python3 scripts/check_model_links_liveness.py report

engine-gate-report: ## Print what each engine cell will actually prove (flag-proven / device-exempt / disabled) from the committed params, before any image is built (issue #625)
	python3 scripts/engine_gate_report.py
build-engine-base: ## Build the shared toolchain base image for BACKEND (cpu|cuda|rocm|vulkan; PUSH=1 publishes + caches in LLGENIE_REGISTRY)
	@test -n "$(BACKEND)" || { echo "Usage: make build-engine-base BACKEND=cpu|cuda|rocm|vulkan [PUSH=1]"; exit 1; }
	python3 scripts/engine_image.py build-base "$(BACKEND)" $(if $(FORCE),--force,) $(if $(PUSH),--push,)
build-engine: ## Build ENGINE's image for one backend from its generated Dockerfile (ARCH=cpu|cuda|rocm|vulkan; FORCE=1 = rebuild with --no-cache, ignoring the layer cache and a stale base; PUSH=1 = publish the hash tag, :<arch> and :latest)
	@test -n "$(ENGINE)" || { echo "Usage: make build-engine ENGINE=<id> [ARCH=cpu|cuda|rocm|vulkan]"; exit 1; }
	python3 scripts/engine_image.py build "$(ENGINE)" $(ARCH_ARGS) $(if $(FORCE),--force,) $(if $(PUSH),--push,)
run-engine: ## Run ENGINE's image: OpenAI API on 127.0.0.1:$(PORT)/v1 as llm-local (MODEL=<path under ~/models | HF id>)
	@test -n "$(ENGINE)" -a -n "$(MODEL)" || { echo "Usage: make run-engine ENGINE=<id> MODEL=<path|hf-id> [ARCH=] [PORT=11434]"; exit 1; }
	python3 scripts/engine_image.py run "$(ENGINE)" $(ARCH_ARGS) --model "$(MODEL)" --port "$(PORT)"
test-published-engine: ## Issue #102: pull ENGINE's ARCH image AS PUBLISHED (no build, digest == :ARCH), then (1) the binary reports its version and (2) the container serves the tiny model and answers "hi" on /v1/chat/completions as llm-local (cpu images, and GPU images of engines with a CPU fallback run without GPU devices; GPU-only engines get the version test)
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make test-published-engine ENGINE=<id> ARCH=cpu|cuda|rocm|vulkan"; exit 1; }
	python3 scripts/engine_image.py pull-published "$(ENGINE)" $(ARCH_ARGS)
	$(MAKE) test-engine-image ENGINE=$(ENGINE) ARCH=$(ARCH)
	# issue #204: the real published image's engine binary must answer its documented flags.
	# It runs in the TEST IMAGE like every other test stage (issue #621): the runner's own python3 has
	# no pytest, so a bare `python3 -m pytest` here fails with "No module named pytest" — which is what
	# every test-published-* job did as soon as the published matrix started carrying rows again.
	@mkdir -p "$(CI_HOME)"
	$(call engine_test,LLGENIE_PUBLISHED_PULLED=1 LLGENIE_TEST_ENGINE="$(ENGINE)" LLGENIE_TEST_ARCH="$(ARCH)") \
		python3 -m pytest -q -p no:cacheprovider tests/test_published_engine_binary.py
	@$(CI_HOME_CLEAN)
	@if python3 -c 'import sys; sys.path.insert(0, "scripts"); import engine_image as ei; sys.exit(0 if ei.chat_testable("$(ENGINE)", "$(ARCH)") else 1)'; then \
	  python3 scripts/engine_smoke.py "$(ENGINE)" $(ARCH_ARGS) --image $(if $(filter cpu,$(ARCH)),,--no-gpu); \
	else echo "[published] $(ENGINE)/$(ARCH) needs a GPU to serve (no CPU fallback): version test only; its cpu image is chat-tested"; fi
push-engine: ## Push ENGINE's image to GHCR only after its binary FILE answers the version/help flags it documents: <registry>/<name>:<pinned-hash-arch> and :<arch>
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
build-engines: ## Build every engine x variant the committed params declare, in PARALLEL — all engines, or ENGINE=<id>, or ARCH=<backend>, or both (JOBS= parallel builds, default: nproc; VERIFY=1 also runs each built image's binary test; FORCE=1 rebuilds every row from scratch, ignoring the layer cache)
	@JOBS="$(if $(JOBS),$(JOBS),$$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4))"; \
	rows=$$(python3 scripts/engine_image.py matrix --json --ci $(if $(ENGINE),--engine "$(ENGINE)",) $(if $(ARCH),--arch "$(ARCH)",)); \
	printf '%s' "$$rows" \
	  | python3 -c 'import json,sys; [print(r["engine"]+" "+r["variant"]) for r in json.load(sys.stdin)["include"] if r["engine"] != "none"]' \
	  | xargs -r -P "$$JOBS" -n 2 sh -c '$(MAKE) build-engine ENGINE=$$0 ARCH=$$1 $(if $(FORCE),FORCE=1,) $(if $(PUSH),PUSH=1,) $(if $(VERIFY),&& $(MAKE) test-engine-image ENGINE=$$0 ARCH=$$1,)' || exit 1
generate-build-engine-params: generate-engine-params ## Alias of generate-engine-params
engine-bump-plan: ## Issue #107: which engines moved upstream (git ls-remote only; ENGINE=<id> to scope)
	@$(PY) scripts/engine_bump.py plan $(if $(ENGINE),--engine $(ENGINE),)
engine-derive: ## Issue #107: derive build params for ENGINE at SHA (or its pin) from the upstream tree (no LLM)
	@test -n "$(ENGINE)" || { echo "Usage: make engine-derive ENGINE=<id> [SHA=<sha>] [OLD_SHA=<sha>]"; exit 1; }
	@$(PY) scripts/engine_bump.py derive "$(ENGINE)" $(if $(SHA),--sha $(SHA),) $(if $(OLD_SHA),--old-sha $(OLD_SHA),)
engine-bump: ## Issue #107: pin ENGINE to its latest upstream commit + derive + apply + regen (no push)
	@test -n "$(ENGINE)" || { echo "Usage: make engine-bump ENGINE=<id>"; exit 1; }
	@$(PY) scripts/engine_bump.py bump "$(ENGINE)"
engine-bump-daily: ## Issue #107: plan -> bump every moved engine (DRY=1 prints the plan, no writes)
	@$(PY) scripts/engine_bump.py bump-daily $(if $(DRY),--dry,)
list-engine-images: ## List every engine x arch variant (CI=1: only CI variants, JSON=1: GitHub matrix JSON; CHANGED=<ref> keeps only images whose tag differs from it)
	@python3 scripts/engine_image.py matrix $(if $(CI),--ci,) $(if $(JSON),--json,) $(if $(CHANGED),--changed $(CHANGED),)
engine-build-matrix: ## The JSON matrix the dispatched engine-build workflow builds: every engine x variant at its committed pin (ENGINE=<id>, ARCH=<backend> narrow it; CI variants only)
	@python3 scripts/engine_image.py matrix --json --ci $(if $(ENGINE),--engine "$(ENGINE)",) $(if $(ARCH),--arch "$(ARCH)",)
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
engine-smoke: ## Install ENGINE via its skill, serve a tiny model, assert llm-local answers (a HOST entry point; CI's per-engine serve check is `make test-engine-stage TEST=serve` inside the engine-image jobs, and `make test-published-engine` on the published image)
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

openspec-validate-all: ## openspec validate --changes: verify the STRUCTURE of every ACTIVE change (the gate a commit's own change cannot slip past, issue #156)
	@if [ "$(HOST_OS)" = Darwin ]; then \
	  command -v openspec >/dev/null 2>&1 || npm install -g @fission-ai/openspec@$(OPENSPEC_VERSION); \
	  openspec validate --changes; \
	else $(RUNTIME) run $(OS_OPTS) openspec validate --changes; fi
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
# The checkout, as a path. A bot job exports REPO as the slug (`asimov-agent/llgenie`) for the sweep
# and the push, and Make treats that environment variable as an override of `REPO :=` above — so a
# gate that mounts $(REPO) hands docker the slug and docker refuses it (run 39727049030: `create
# asimov-agent/llgenie: includes invalid characters for a local volume name`). A mount needs a path.
# `override` ignores the environment; the slug stays available to the bot targets through $(REPO).
override ROOT := $(shell pwd)
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
# Token names only. docker copies the values from the environment; they stay off argv.
TEST_OPTS := --rm -u root -v "$(ROOT)":/repo:rw -w /repo -e HOME=/root -e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN $(WORKTREE_MOUNT)
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
	-v /var/run/docker.sock:/var/run/docker.sock -v "$(ROOT)":"$(ROOT)":rw -w "$(ROOT)" \
	-e HOME="$(CI_HOME)" -e LLGENIE_REGISTRY -e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN -e RUNTIME=docker $(WORKTREE_MOUNT)
engine_test = $(ENGINE_TEST_ARGS) $(foreach v,$(1),-e $(v)) $(TEST_IMG)
ENGINE_TEST_RUN := $(call engine_test,)
# .ci-home is written by root inside the container: remove it from a container too.
CI_HOME_CLEAN := $(RUNTIME) run --rm -v "$(ROOT)":/r $(TEST_IMG) rm -rf /r/.ci-home
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

publish-ci-images: ## CI job ci-images: build + push the test and OpenSpec images ONLY when their hash tag is not on GHCR yet. The AGENT image is NOT here: the default GITHUB_TOKEN is denied "Create organization package" for a brand-new package (the first llgenie/agent publish), so it goes out through publish-agent-image.yml with the owner PAT, deliberately and by hand
	python3 scripts/ci_images.py publish test openspec

publish-agent-image: ## Build + push ONLY the agent (Hermes) image to GHCR (linux/amd64: it builds Hermes at build time, which times out under arm64 emulation) when its hash tag is not there yet, and point :latest at that hash even when the hash is already published. Set FORCE=--force to rebuild + push even when the hash is already there (issue #990). The dedicated job for the Hermes container (issues #222/#238/#248); guarded to owner/collaborators.
	python3 scripts/ci_images.py publish agent $(FORCE)

agent-image-push-check: ## Prove the GHCR credential can PUSH the agent image BEFORE the (up to 60-minute) build: ask the registry for a push-scoped token, then initiate the cheapest real write there is (an empty blob upload, no data). Prints the registry's own refusal and exits non-zero when the credential may not push (issue #335)
	@test -n "$$GHCR_TOKEN" || { echo "ERROR: GHCR_TOKEN is unset - this target asks GHCR to prove a credential can push the llgenie/agent package"; exit 1; }
	python3 scripts/ci_images.py pushcheck agent

agent-image: ## The agent (Hermes) image: pull ghcr.io/<registry>/llgenie/agent:latest, else build it here
	python3 scripts/ci_images.py ensure agent

agent-image-pull: ## CI: pull ghcr.io/<registry>/llgenie/agent:latest as llgenie/agent:latest; fails if that tag is missing, never builds
	python3 scripts/ci_images.py pull agent

ci-image-refs: ## Print the GHCR refs of the CI images (test, openspec, agent) for the current Dockerfiles + lockfiles
	@python3 scripts/ci_images.py ref

test-variant-image: ## Build the CUDA toolkit + python variant-build image locally (the variant-build matrix is no longer a pipeline job; this reproduces it by hand)
	# The lockfiles are build-time inputs copied from tools/ (the ONE generator of a compiled pin),
	# in a TEMP context — never written into the checkout, where a stale copy becomes a finding the
	# scan can never clear (issue #787, the same shape as scripts/ci_images.py::context).
	@ctx=$$(mktemp -d) && trap 'rm -rf "$$ctx"' EXIT && \
		cp containers/ci-variant/Dockerfile "$$ctx/" && \
		cp tools/requirements.txt tools/requirements-dev.txt "$$ctx/" && \
		$(RUNTIME) build -t $(VARIANT_IMG) "$$ctx"
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

# internal CI seam (issue #1000): the `-m network` twin of test-unit, run by the admitted `ci-network` pipeline — every test the hermetic gate excludes by marker runs HERE, never silently skipped; not user-facing and no `##` help line on purpose (engine-matrix-pushed precedent)
test-unit-network: bash-check
	$(MAKE) bash-check
	$(TEST_RUN) python scripts/unit_tests.py run --marker network

test-unit: ## Hermetic unit tests (containerized) — the suite is DISCOVERED, not enumerated: scripts/unit_tests.py selects every tests/test_*.py minus the dated exclusions in tests/fixtures/unit-suite.json (issue #393)
	$(TEST_RUN) python scripts/unit_tests.py run

# Live GitHub release reads. Linux only: the macOS runner cannot reach
# api.github.com, and TensorFold publishes no macos-x86_64 archive.
test-hub-live: ## The live-Hub checks kept OUT of the hermetic gate (issue #438): the README's trend links answer, and a missing model really downloads — network + a multi-hundred-MB fetch
	$(TEST_RUN) python -m pytest tests/test_trend_pick.py::test_the_vendored_registry_links_all_answer tests/test_trend_pick.py::test_readme_links_answer_and_a_broken_copy_is_caught tests/test_trend_pick.py::test_select_downloads_a_missing_model_for_real -p no:cacheprovider -q
test-strata-live: ## The Strata download/serve checks kept OUT of the hermetic gate (issue #437): Strata's pinned commit is fetched over git, its GGUF choices come from the live Hub, and its real server answers — network + a real install
	$(TEST_RUN) python -m pytest tests/test_strata_download.py -p no:cacheprovider -q
test-engine-bump-live: ## The PINNED engine's release archive: list, classify, checksum, download, run — the version is read from the engine's params at run time, never a literal (issue #830)
	$(TEST_RUN) python -m pytest tests/test_engine_bump.py::test_derive_reports_the_live_release_archives tests/test_engine_bump.py::test_the_pinned_release_is_native_archives tests/test_engine_bump.py::test_the_pinned_release_archive_unpacks_and_runs -p no:cacheprovider -q

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
	"$(AGENTS_READ_VENV)/bin/python" -m pytest tests/test_agent_skills_live.py --noconftest -p no:cacheprovider -q

test-agent-skills-live: agents-read-venv ## Prove Hermes really LOADS every bot leg's project skill: each leg's `-s` list through hermes-agent's own preload path, in this checkout (issue #577)
	@echo "==> test-agent-skills-live: preloading every leg's skills through hermes-agent ($(AGENTS_READ_VENV))"
	"$(AGENTS_READ_VENV)/bin/python" -m pytest tests/test_agent_skills_live.py --noconftest -p no:cacheprovider -q

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

test: ## Full fast suite (unit + install; hermetic files in the container, install artifacts on the host)
	# tests/test_install.py asserts the REAL ~/bin/llgenie + ~/models, which a `--rm` container with
	# HOME=/root can never hold: in the container those six assertions can only ever fail (#317). The
	# hermetic files run here — the `fast` group the roster records (issue #403), so this recipe
	# names no test file; the install assertions run on the host, where the artifacts live.
	$(TEST_RUN) python scripts/unit_tests.py run --group fast
	$(MAKE) test-install-host

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
	$(MAKE) check-trend-list-matrix
	$(MAKE) skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json
	$(MAKE) check-engine-skill-gap
	$(MAKE) check-engine-params
	$(MAKE) check-engine-coverage
	$(MAKE) check-engine-source
	$(MAKE) check-engine-launchers
	$(MAKE) check-model-links
	$(MAKE) check-wiring
	$(MAKE) check-secret-output
	$(MAKE) check-docs
	$(MAKE) check-dispatch-forms
	$(MAKE) check-pr-hygiene
	$(MAKE) check-issue-bodies
	$(MAKE) check-pr-authors
	$(MAKE) check-workflows
	$(MAKE) check-module-names
	$(MAKE) check-scanner-images
	$(MAKE) check-security-scan
	$(MAKE) check-security-issues
	$(MAKE) check-security-bumps
	$(MAKE) check-security-bot
	$(MAKE) check-actions
	$(MAKE) check-renovate
	$(MAKE) check-agent-skills
	$(MAKE) check-agent-model
	$(MAKE) issue-bot-gates
	$(MAKE) issue-bot-gates-check

ci-agents-read: bash-check ## CI job agents-read: make test-agents-read (Python 3.12 venv -> AGENTS.md scan -> guard tests)
	$(MAKE) test-agents-read

ci-openspec: bash-check ## CI job openspec: validate the STRUCTURE of every active change and assert none has an unchecked task — a hardcoded change name let an invalid spec land (issue #156)
	$(MAKE) openspec-validate-all
	$(MAKE) openspec-tasks-check

ci-cpu-health: bash-check ## CI job cpu-health: Linux answers "hi" through the llama.cpp image; macOS never starts an engine image
	$(MAKE) test-health

ci-top-tier: bash-check ## CI job top-tier: same targets on both OSes (venv on macOS, test image on Linux)
	$(MAKE) test-top-tier-ci && $(MAKE) test-top-tier-serve-ci && $(MAKE) test-top-tier-cli-ci

# The gate below branches on $(HOST_OS), so it lives AFTER `HOST_OS := $(shell uname -s)`:
# make evaluates ifeq while it parses the file, and a conditional placed before that line
# would see an empty HOST_OS and take the Linux branch on macOS too.
ci-wait-engine-images: bash-check ## Host/consumer helper (issue #169): wait until every image `make install` pulls for ARCH is published; names and fails on a tag that never appears. No longer a CI gate: ci-install is product-only and the engine-build producer installs the just-published image directly (#1027). macOS pulls no engine image (issue #120).
ifeq ($(HOST_OS),Darwin)
	@echo "ci-wait-engine-images: macOS pulls no engine image (issue #120), nothing to wait for"
else
	python3 scripts/install_engine_launchers.py --wait-published $(if $(ARCH),--arch $(ARCH),) $(if $(ENGINES),--engines $(ENGINES),)
endif

ci-install: bash-check ## CI job install (issue #1027): PRODUCT-ONLY — prepare the environment, install the llgenie tool (venv + launcher, no engine pull/test), then the installed llgenie dry run, the CLI arg surface and make uninstall, as separate steps. The inference-engine install-test lives in the engine-build producer's `test-engine-install`. macOS never runs a container.
	$(MAKE) test-env
	$(MAKE) ci-install-product
	$(MAKE) ci-install-dry
	$(MAKE) ci-install-dry-args
	$(MAKE) ci-install-uninstall

ci-install-product: bash-check # Internal CI seam (issue #1027, product-only like test-engine-install): install the llgenie tool WITHOUT pulling or testing any inference engine — venv + launcher + smoke only. The engine install-test is the engine-build producer's `test-engine-install`. Runs inside the test container (which has the repo's python 3.11), like every other ci-install stage.
ifeq ($(HOST_OS),Darwin)
	$(MAKE) venv-install
	$(MAKE) link
	$(MAKE) smoke
else
	$(ENGINE_TEST_RUN) sh -c 'make venv-install && make link && make smoke'
endif

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

ci-install-dry-args: bash-check ## The INSTALLED launcher's own argument surface, dry run, over the mocked (arch, vram, ram) grid (issue #236): the wrapper a user runs must reach the same code path
ifeq ($(HOST_OS),Darwin)
	$(TEST_RUN) python -m pytest tests/test_cli_dry_run_matrix.py -p no:cacheprovider -q
else
	$(ENGINE_TEST_RUN) sh -c 'python3 -m pytest tests/test_cli_dry_run_matrix.py -p no:cacheprovider -q'
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

ci-engines: bash-check ## Per-backend engine install for a host (BACKEND=cpu|cuda|rocm|vulkan|metal -> make test-install-published / each native-Metal engine + \"hi\" via scripts/ci_engines.py). No longer a CI stage: the engine install/serve test lives in the engine-build producer (#1027).
	@test -n "$(BACKEND)" || { echo "Usage: make ci-engines BACKEND=cpu|cuda|rocm|vulkan|metal"; exit 1; }
	python3 scripts/ci_engines.py $(BACKEND)

ci-slow-rows: ## CI: decide which heavy rows this run schedules — `linux / top-tier` runs on every non-PR event (push to main) and on a PR only with the `ci:slow` label (scripts/ci_slow_rows.py, issue #859)
	python3 scripts/ci_slow_rows.py decide --event "$$EVENT" --labels "$$LABELS"

ci-free-disk: ## CI: free runner disk for the large engine images (Linux runner: drop preinstalled SDKs; macOS runner: report only)
	@if [ "$$(uname -s)" = Linux ]; then sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL; \
	else echo "[ci-free-disk] $$(uname -s) runner: nothing to free"; fi
	@df -h /

test-engine-stage: ## CI engine-image post-build test, ONE step for every image: TEST=serve -> binary flags (make test-engine-image) AND the OpenAI API answer (make test-engine); TEST=detect -> binary flags only (make test-engine-image)
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect"; exit 1; }
	@case "$(TEST)" in \
	  serve)  $(MAKE) test-engine-image ENGINE="$(ENGINE)" ARCH="$(ARCH)" && \
	          $(MAKE) test-engine ENGINE="$(ENGINE)" ARCH="$(ARCH)" ;; \
	  detect) $(MAKE) test-engine-image ENGINE="$(ENGINE)" ARCH="$(ARCH)" ;; \
	  *) echo "[test-engine-stage] TEST must be serve or detect, got '$(TEST)'"; exit 1 ;; \
	esac

help:
	@echo "Engine images (issue #98, plain make, no LLM):"
	@echo "  make generate-engine-params      skills -> containers/engines/{params,dockerfiles,base} (the ONLY step that reads skills)"
	@echo "  make sync-quant-catalog          regenerate data/trending-quant-catalog.json + fixture (the HF class table: model -> engine -> arch + real quant plans), from the registry + live Hub; validates the newly-added links vs the prior generated table"
	@echo "  make check-quant-catalog         CI: fail if the committed quant catalog differs from what the generator produces"
	@echo "  make render-trend-list-matrix    rewrite tests/fixtures/trend-list-matrix.json (the trending list per arch, vram, ram)"
	@echo "  make check-trend-list-matrix     CI: fail if that committed list differs from matrix() on the vendored registry"
	@echo "  make render-engine-skill-gap     rewrite data/engine-skill-gap.json (per-engine list + the models no engine can offer)"
	@echo "  make check-engine-skill-gap      CI gate: a registry engine with no skill and no dated decision in data/unsupported-engines.json, a stale decision, or a stale file"
	@echo "  make engine-skill-gap            show the gap: shipped / known-unsupported / NEW-unresolved engines"
	@echo "  make spawn-engine-skill-issues   open one tracking issue per NEW unskilled engine (the weekly sync runs this)"
	@echo "  make registry-change-report      print what the vendored registry changed vs HEAD"
	@echo "  make sync-change-issue           open ONE issue stating the change (the weekly sync runs this)"
	@echo "  make check-wiring                CI: fail when a test/script is wired to no make target, or only to one CI never runs (tests/fixtures/host-only-wiring.json records the deliberate ones), or when a .PHONY entry names no target or a target that runs nothing"
	@echo "  make check-secret-output         CI: fail when any file prints a secret's VALUE (an echo of a token variable), passes it on a command line (a value after -e), runs under a shell xtrace, dumps the environment around it, or commits a credential-shaped literal"
	@echo "  make wiring-report               show how every test/script is wired (target + whether CI runs it) and the host-only exceptions"
	@echo "  make issue-bot-dispatch          the issue-implementer dispatcher (issue #248): cap 3/day -> pick one labeled/ready issue -> claim -> write issue.md + branch"
	@echo "  make issue-bot-open-pr          open the draft-free PR linking ISSUE from BRANCH (never merges)"
	@echo "  make issue-bot-gates            re-check the FAST gates in order before the bot pushes (lint, workflows, wiring, docs, PR hygiene, OpenSpec tasks), stopping at the first failure and naming it (issue #475)"
	@echo "  make issue-bot-gates-check      CI: fail when a ci-unit gate is classified nowhere, a fast gate is unwired, or the bot's gate step is not between the detection and the push (issue #475)"
	@echo "  make code-review-scan           the code-review bot: read the tree + the pipelines -> findings (REPO=; STATIC=1 skips the checks that read the GitHub API; no model spend, files nothing)"
	@echo "  make code-review-file           file ONE issue per NEW finding, capped per run (REPO=; CAP= per run, default 3; DRY=1 previews) — the bot's whole output is issues"
	@echo "  make run-failure-reactor        route a failed CI run to a remedy (REPO=; RUN_ID=; DRY=1 previews): a pushable same-repo PR -> dispatch the fix-bot; else file ONE deduped issue labelled agent:implement (issue #286)"
	@echo "  make implement-issue             the shared Hermes agent step: read issue.md + AGENTS.md, implement, run the gates, push nothing (NOUS_API_KEY from a secret)"
	@echo "  make hermes-smoke               one real Hermes call through the implementer alias (die in seconds)"
	@echo "  make agent-jev-preflight           report whether the JEV decision layer is available in the agent image (never blocks a run; NERVE_REQUIRE=1 verifies the image instead) — issue #238"
	@echo "  make check-docs                  CI: fail when a user-facing make target is undocumented, an exception is stale, an agent-wiki/ note is not indexed in CHANGES.md, or README.md carries change history"
	@echo "  make docs-report                 show every user-facing make target (documented / missing / recorded exception) and each work record's issue references"
	@echo "  make check-pr-authors            CI: fail when a PR commit is authored through an allowlisted email address, when a Co-authored-by trailer names anyone else, or when a producer commits off the allowlist — PR_BASE/PR_HEAD bound the range (issue #345)"
	@echo "  make pr-authors-report           show every commit in the range with its author verdict, and the identity each producer assigns"
	@echo "  make build-engine ENGINE=<id> [ARCH=cpu|cuda|rocm|vulkan] [PUSH=1]   build from the generated Dockerfile"
	@echo "  make build-engine-<id>-<arch>    e.g. build-engine-vllm-cuda, build-engine-llama.cpp-prism-rocm"
	@echo "  make build-engines ARCH=<arch>   every engine for one arch"
	@echo "  make run-engine ENGINE=<id> MODEL=<m> [PORT=11434]   OpenAI API at http://127.0.0.1:PORT/v1 (llm-local)"
	@echo "  make list-engine-images | ci-engine-images [WATCH=1]"
	@echo
	@echo "Targets:" \
		"install (venv+launcher+symlink+smoke), venv-install, link, smoke,"
	@echo "         test-unit, test-install, test-health (endpoint answers 'hi'), test,"
	@echo "         download-test-model, openspec-validate, openspec-new/status,"
	@echo "         loop (chained runner), loop-harness, chained, uninstall,"
	@echo
	@echo "Daily sync (issue #107):"
	@echo "  make engine-bump-plan [ENGINE=<id>]   which engines moved upstream (git ls-remote only)"
	@echo "  make engine-derive ENGINE=<id> [SHA=] derive build params from the upstream tree (no LLM)"
	@echo "  make engine-bump ENGINE=<id>          pin + derive + apply + regen (no push)"
	@echo "  make engine-bump-daily [DRY=1]        plan -> bump every moved engine; DRY=1 prints only"
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
