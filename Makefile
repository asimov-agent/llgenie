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
	test test-unit test-agents-read agents-read-venv test-install test-install-ci test-install-host test-install-trend test-health test-health-host download-test-model \
	test-image test-image-pull openspec-image-pull publish-ci-images publish-agent-image agent-image agent-image-pull ci-image-refs test-clean lint lint-fix loop loop-harness chained \
	build-server build-variant serve-variant test-serve-variant stop-serve-variant install-prism-cpu install-upstream-cpu \
	install-prism-cuda install-upstream-cuda install-prism-metal install-upstream-metal \
	sync-registry check-registry skills-validate engine-list engine-hardware engine-plan engine-check engine-install engine-detect engine-smoke test-engine ci-engine-images build-engine-base build-engines generate-build-engine-params test-engine-image push-engine test-published-engine test-install-published engine-launchers test-built-engine test-uninstalled \
	sync-quant-catalog check-quant-catalog render-trend-list-matrix check-trend-list-matrix render-engine-skill-gap check-engine-skill-gap \
	engine-skill-gap engine-skill-gap-md spawn-engine-skill-issues sync-strata-models check-strata-models check-wiring wiring-report check-secret-output secret-output-report \
	queued-alarm fix-loop fix-loop-image fix-bot-sweep fix-bot-report agent-image-ref issue-bot-dispatch issue-bot-open-pr issue-bot-image \
	issue-bot-triage issue-bot-verdict implement-issue hermes-smoke agent-jev-preflight code-review-scan code-review-file rebase-bot-sweep rebase-bot \
	rebase-bot-agent check-docs docs-report check-pr-hygiene pr-hygiene-report issue-refiner-pick issue-refiner issue-refiner-apply check-dispatch-forms dispatch-forms-report \
	engine-bump-rebase generate-engine-params check-engine-params build-engine run-engine stop-engine list-engine-images ci-lint ci-unit ci-agents-read \
	ci-openspec ci-cpu-health ci-top-tier ci-install ci-install-dry-args ci-free-disk test-engine-stage bot-sync-main bot-sync-branch

# ---- container runtime: docker -------------------------------------------
RUNTIME ?= docker
OS_IMG := llgenie/openspec:latest

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
sync-registry: ## Download trending-local-llms data/models.json into data/models.json (validated; written only when changed)
	python3 scripts/sync_registry.py sync
check-registry: ## Validate the vendored data/models.json + fail when the sync LOST anything vs the committed copy (CI unit job)
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
spawn-engine-skill-issues: ## Open one tracking issue per NEW unskilled registry engine (the sync job runs this; DRY=1 previews, REPO= picks the repo)
	python3 scripts/engine_skill_gap.py spawn $(if $(REPO),--repo $(REPO),) $(if $(DRY),--dry,)
# ---- issue-bot: one issue per run, at most 3/day (issue #248) -----------------
# The dispatcher is deterministic (no LLM): cap -> pick ONE -> claim -> issue.md
# + branch. `implement-issue` is the shared Hermes agent step (AGENTS.md is the
# authority the agent reads; #238 wires the token/plugin into the agent image).
# ---- rebase-bot: keep the open PRs on `main` (issue #246). ONE PR per 6-hourly run; a conflict
# is handed to the agent; the result is verified structurally and pushed with --force-with-lease
# to the PR's OWN head remote (a fork PR goes to the fork). It never merges.
rebase-bot-sweep: ## Which ONE open PR needs rebasing (BEHIND/DIRTY against main): prints action/pr/head_* and the reason for every pass-over
	python3 scripts/rebase_bot_sweep.py --repo $(if $(REPO),$(REPO),asimov-agent/llgenie) $(if $(OWN_FORK),--own-fork $(OWN_FORK),)

rebase-bot-agent: ## Ask Hermes to resolve a stopped rebase (the conflict prompt arrives on STDIN); runs INSIDE the agent image
	@python3 scripts/ci_images.py ensure agent
	@$(RUNTIME) run --rm -i --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e TYPESAFE_API_KEY -e OPENROUTER_API_KEY -e OPENCODE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_IMAGE) bash -lc 'make _rebase-bot-agent'

_rebase-bot-agent: # (internal) the host recipe: read the conflict prompt on stdin, resolve, stage
	hermes -z "$$(cat)" $(nous-alias) --reasoning medium --yolo

rebase-bot: ## Rebase ONE PR onto main (agent-resolved conflicts), verify the structure, then push --force-with-lease to the PR's head remote. Never merges. Needs PR=/HEAD_BRANCH= [HEAD_REPO=] [DRY=1]
	@test -n "$(PR)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make rebase-bot PR=<n> HEAD_BRANCH=<branch> [HEAD_REPO=<owner>] [REPO=] [DRY=1]"; exit 1; }
	PR=$(PR) HEAD_BRANCH="$(HEAD_BRANCH)" HEAD_REPO=$(if $(HEAD_REPO),$(HEAD_REPO),asimov-agent) \
	  REPO=$(if $(REPO),$(REPO),asimov-agent/llgenie) $(if $(DRY),DRY=1,) scripts/rebase_bot.sh
# ---- issue-refiner: reviews NOT-yet-implemented issues on the implementer's spare capacity
# (issue #263). One issue per run, ONE comment + the `agent:refined` label, and never a PR.
issue-refiner-pick: ## Spare capacity (the implementer's cap is spent)? -> the oldest issue that is not decided, claimed or already PR'd -> refine-in.md (DRY=1 previews; REPO= picks the repo)
	python3 scripts/issue_refiner.py pick --repo $(if $(REPO),$(REPO),asimov-agent/llgenie) $(if $(DRY),--dry,)
issue-refiner: ## Hermes REVIEWS the picked issue (reads refine-in.md: the thread + the review instruction) and writes its verdict to refine.md. No branch, no PR, nothing else touched; runs INSIDE the agent image
	@$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY -e OPENROUTER_API_KEY -e OPENCODE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_IMAGE) bash -lc 'make _issue-refiner'
_issue-refiner: # (internal) the host recipe the agent image runs: the review, not the code
	hermes -z "Load AGENTS.md for rules. Read refine-in.md at the repo root: it carries an issue, its WHOLE comment thread (oldest first), and the review instruction. Follow that instruction and write your verdict to refine.md at the repo root in exactly the required shape (a REFINE: line plus the RESTATED:/REASON: blocks the chosen verdict requires). HARD RULES: this is a REVIEW, not an implementation - do NOT write any code, do NOT create a branch, do NOT push, do NOT open a PR, do NOT comment on the issue yourself, and do NOT modify any file other than refine.md. If the thread leaves a decision open, name it as a question in the restatement instead of deciding it." $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
issue-refiner-apply: ## Apply the review in refine.md: ONE comment on the issue + the agent:refined label (never a PR; refuses a `refined` verdict with no RESTATED block)
	@test -n "$(ISSUE)" || { echo "Usage: make issue-refiner-apply ISSUE=<n> [REPO=<owner/repo>]"; exit 1; }
	python3 scripts/issue_refiner.py apply refine.md --repo $(if $(REPO),$(REPO),asimov-agent/llgenie) --issue $(ISSUE)

issue-bot-dispatch: ## The issue-implementer's dispatcher: cap (3/day) -> pick one labeled/ready issue -> claim -> write issue.md + branch (REPO= issue-bot.yml sets it; FORCE_ISSUE= pins a manual run; DRY=1 previews)
	python3 scripts/issue_implementer.py dispatch --repo "$(REPO)" $(if $(FORCE_ISSUE),--force-issue $(FORCE_ISSUE),) $(if $(DRY),--dry,) $(if $(TODAY),--today $(TODAY),)
issue-bot-open-pr: ## Open the draft-free PR linking ISSUE from BRANCH (never merges; REPO=/ISSUE=/BRANCH= from the workflow)
	@test -n "$(ISSUE)" && test -n "$(BRANCH)" || { echo "Usage: make issue-bot-open-pr REPO=<owner/repo> ISSUE=<n> BRANCH=<agent/issue-n-slug>"; exit 1; }
	python3 scripts/issue_implementer.py open-pr --repo "$(REPO)" --issue $(ISSUE) --branch "$(BRANCH)" --title "issue-bot implementation" --wants "Verification notes land on the PR as CI runs it."
# The agent step: Hermes reads issue.md + AGENTS.md at the repo root and
# implements it. AGENTS.md is the authority (Makefile-driven verification, no
# skipped tests, business logic never mocked, one make path per stage, wiring).
# Runs on the CI runner with NOUS_API_KEY from a secret; #238 wires the
# token/plugin into the agent image. The model alias matches the sibling repo.
# Hermes's bundled `nous` provider is OAuth-only, so `--provider nous` cannot work with a
# secret. The image's install script writes a custom-provider alias instead (provider=custom,
# base_url=the Nous OpenAI-compatible endpoint, key_env=NOUS_API_KEY) and this is the model
# name every call uses. `-m` is the MODEL flag (a bare `-m "text"` sets the model to text).
nous-alias := -m nous-deepseek
HERMES_REASONING ?= low
# The bots run INSIDE the agent image (issues #222/#238/#248): Hermes, git, gh and the docker
# CLI are installed when the image is built, so a runner never installs the agent on the fly —
# and the image a job uses is the one built from THIS commit's Dockerfile + install script
# (the ref is their hash, so it cannot drift from the workflow that names it).
# NOUS_API_KEY and GH_TOKEN travel as run-time env; nothing is baked into the image.
# `ensure` pulls the published image of these inputs, or builds the same Dockerfile locally, and
# tags it under this name either way — so this works on a dev host and on a runner. The tag hash
# pins it to the exact Dockerfile THIS commit carries.
AGENT_IMAGE := llgenie/agent:latest

issue-bot-image: ## Build/pull the agent image the issue-bot runs in (the same image the fix-bot uses; alias of agent-image)
	python3 scripts/ci_images.py ensure agent

issue-bot-triage: ## Hermes REVIEWS the issue (issue.md: body + the whole comment thread + the decision block) and writes its verdict to triage.md (implement | refine | close). No PR, nothing else touched; runs INSIDE the agent image
	@python3 scripts/ci_images.py ensure agent
	@$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  $(AGENT_IMAGE) bash -lc 'make _issue-bot-triage'

_issue-bot-triage: # (internal) the host recipe the agent image runs: the decision, not the code
	hermes -z "Load AGENTS.md for rules. Read issue.md at the repo root: it carries the issue, its WHOLE comment thread (oldest first), and the decision instruction. Follow that instruction and decide ONE verdict - implement, refine or close - then write it to triage.md at the repo root in exactly the required shape (a TRIAGE: line, plus REFINED:/EVIDENCE:/REASON: blocks as that verdict requires). HARD RULES: do NOT implement anything, do NOT modify any file other than triage.md, do NOT create a branch, do NOT push, do NOT comment on the issue yourself. A close without an EVIDENCE: block is refused by the next step, so cite what you checked. If a decision is still open in the thread, that is a refine, not a guess." $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

issue-bot-verdict: ## Apply the agent's TRIAGE verdict from triage.md: implement -> nothing (the PR path runs), refine -> ONE comment + agent:refined (no PR), close -> comment with the cited evidence + agent:closed (refused without EVIDENCE)
	@test -n "$(ISSUE)" || { echo "Usage: make issue-bot-verdict ISSUE=<n> [REPO=<owner/repo>]"; exit 1; }
	python3 scripts/issue_implementer.py apply-verdict triage.md --repo $(if $(REPO),$(REPO),asimov-agent/llgenie) --issue $(ISSUE)

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

agent-jev-preflight: ## Prove the JEV engine is active in the agent image; every bot workflow runs it with NERVE_REQUIRE=1, so a job whose engine is off does not start. NERVE_GATE_SKIP_PROVIDER=1 skips the live provider call
	@python3 scripts/ci_images.py ensure agent
	@$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e TYPESAFE_API_KEY -e OPENROUTER_API_KEY -e OPENCODE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE -e NERVE_GATE_SKIP_PROVIDER \
	  $(AGENT_IMAGE) bash -lc 'make _agent-jev-preflight'
# The code-review bot (issue #269): it reads the TREE and the PIPELINES and files what is
# actually wrong. Its whole output is issues — analysis, never implementation (AGENTS.md,
# #231) — so it never edits a file, never opens a PR and never merges; each issue carries the
# evidence the finding was derived from, so a reviewer can check the claim without re-deriving
# it. `scan` is free (no model, no API writes); `file` writes issues and dedups by a marker in
# the body, so a re-run of an unchanged tree files nothing.
code-review-scan: ## The code-review bot's checks: tree + pipelines -> findings (REPO=; STATIC=1 skips the checks that read the GitHub API; JSON=1 for machine output; no model spend, writes nothing)
	python3 scripts/code_review.py scan --repo "$(REPO)" $(if $(STATIC),--static-only,) $(if $(JSON),--json,)
code-review-file: ## File ONE issue per NEW code-review finding, capped per run (REPO=; CAP= issues per run, default 3; DRY=1 previews) — never edits code, never merges
	@test -n "$(REPO)" || { echo "Usage: make code-review-file REPO=<owner/repo> [CAP=3] [DRY=1]"; exit 1; }
	python3 scripts/code_review.py file --repo "$(REPO)" $(if $(CAP),--cap $(CAP),) $(if $(DRY),--dry,)

implement-issue: ## Implement issue.md with Hermes INSIDE the agent image (AGENTS.md is the authority; NOUS_API_KEY/GH_TOKEN from secrets; runs the gates; pushes nothing)
	@python3 scripts/ci_images.py ensure agent
	@$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e GH_TOKEN -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY -e OPENROUTER_API_KEY -e OPENCODE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_IMAGE) bash -lc 'make _implement-issue'

hermes-smoke: ## One real Hermes call through the alias the implementer uses, inside the agent image (die in seconds, not after 20 min)
	@test -n "$$NOUS_API_KEY" || { echo "NOUS_API_KEY unset - refusing to spend time on a dead key"; exit 1; }
	@python3 scripts/ci_images.py ensure agent
	@$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo -e NOUS_API_KEY \
	  -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_IMAGE) bash -lc 'make _hermes-smoke'

# Inside the image: the JEV preflight first, so the run knows whether the decision layer is
# there. It reports; it never blocks.
_agent-jev-preflight: # (internal) report whether the JEV layer is available in this home.
# Invoked inside the agent image by the public `agent-jev-preflight` target, and by
# `_implement-issue` before any agent work.
	/usr/local/bin/agent_jev_preflight.sh

_implement-issue: # (internal) the host recipe: implement issue.md with Hermes. Invoked
# inside the agent image by the public `implement-issue` target.
	$(MAKE) _agent-jev-preflight
	hermes -z "Load AGENTS.md for rules. The issue to implement is issue.md at the repo root - read it FIRST (and the linked OpenSpec change if present) and implement exactly its acceptance criteria; do not widen the scope. HARD RULES: (1) run every gate through the Makefile and fix what they report; (2) never weaken or mock a test to get green; (3) a test or script you add must be named by a make target (nothing dead); (4) follow the repo's issue -> branch -> OpenSpec -> code -> PR lifecycle. Do not push, do not merge, do not touch main." $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
_hermes-smoke: # (internal) one real Hermes call. Invoked inside the agent image by
# the public `hermes-smoke` target.
	@test -n "$$NOUS_API_KEY" || { echo "NOUS_API_KEY unset - refusing to spend time on a dead key"; exit 1; }
	hermes -z "Reply with exactly: ok" $(nous-alias) --reasoning low --yolo
sync-strata-models: ## Write data/strata_models.json from Strata's setup.py at the skill's pinned commit (the GGUF files Strata runs)
	python3 scripts/strata_models.py sync
check-strata-models: ## CI: fail when data/strata_models.json differs from Strata's setup.py at the pinned commit
	python3 scripts/strata_models.py check
engine-bump-rebase: ## Rebase every open chore/engine-bump-* PR onto the latest main (DRY=1 prints what it would do and pushes nothing)
	python3 scripts/engine_bump_rebase.py $(if $(DRY),--dry,)
check-dispatch-forms: ## CI: fail when a dispatchable workflow does not state the work it will do: name, documented dispatch inputs, header block, and the README table
	python3 scripts/check_dispatch_forms.py check
dispatch-forms-report: ## Print the README's dispatch table (generated from the workflow files; paste it between the dispatch-forms markers)
	python3 scripts/check_dispatch_forms.py report
queued-alarm: ## Report jobs stuck in `queued` far too long (a runner that never picks them up, issue #254); COMMENT=1 delivers the report, DRY=1 previews it
	python3 scripts/queued_run_alarm.py --repo $(if $(REPO),$(REPO),asimov-agent/llgenie) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(COMMENT),--comment,) $(if $(DRY),--dry,)

fix-loop-image: ## Run the fix-bot loop inside the agent image (the same image the workflow uses); AGENT_IMAGE overrides the resolved ref, LOG=path tees the output
	@img=$$(if [ -n "$(AGENT_IMAGE)" ]; then echo "$(AGENT_IMAGE)"; else python3 scripts/ci_images.py ref agent; fi); \
	echo "agent image: $$img"; \
	$(RUNTIME) run --rm --init -v "$$PWD:/repo" -w /repo \
	  -e NOUS_API_KEY -e GH_TOKEN -e FIX_CHECK -e FIX_ROUNDS \
	  -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  "$$img" bash -lc 'scripts/agent_jev_preflight.sh && scripts/fix_loop.sh' 2>&1 | tee "$(if $(LOG),$(LOG),/tmp/fix-loop.log)"

fix-bot-sweep: ## Which red PR the fix-bot should repair, and dispatch it (DRY=1 previews; needs gh)
	python3 scripts/fix_bot_sweep.py --repo $(if $(REPO),$(REPO),asimov-agent/llgenie) --check "$(if $(CHECK),$(CHECK),make ci-unit)" --max-attempts $(if $(ATTEMPTS),$(ATTEMPTS),3) $(if $(DRY),--dry,)

fix-bot-report: ## Render the fix-bot's failure report from the loop's report file (REPORT=<path>; the same command the workflow uses to comment)
	python3 scripts/fix_bot_report.py "$(if $(REPORT),$(REPORT),/tmp/fix-report.txt)" --command "$(if $(CHECK),$(CHECK),make ci-unit)"

agent-image-ref: ## Print the GHCR ref of the agent (Hermes) image for the current Dockerfile + install script
	@python3 scripts/ci_images.py ref agent

fix-loop: ## Run the PR fix-bot loop locally against the failing check (scripts/fix_loop.sh; needs an agent on PATH)
	FIX_ROUNDS="$(if $(ROUNDS),$(ROUNDS),3)" FIX_CHECK="$(if $(CHECK),$(CHECK),make ci-unit)" scripts/fix_loop.sh

check-secret-output: ## CI: fail when any file prints a secret's VALUE, passes it on a command line, xtraces it, dumps the environment around it, or commits a credential-shaped literal
	python3 scripts/check_secret_output.py check
secret-output-report: ## Show which files name a secret-shaped variable, and whether any prints it
	python3 scripts/check_secret_output.py report
check-wiring: ## CI: fail when a test/script is wired to no make target or only to one CI never runs, when a recorded host-only exception is stale, or when a workflow calls a make target that does not exist
	python3 scripts/check_wiring.py check
wiring-report: ## Show how every test/script is wired (which make target, and whether CI runs it) and the recorded host-only exceptions
	python3 scripts/check_wiring.py report
check-docs: ## CI: fail when a user-facing (## help) make target is not documented in README.md, when a recorded exception is stale, or when an agent-wiki/ work record references no issue or PR (issue #257)
	python3 scripts/check_docs.py check
docs-report: ## Show every user-facing make target as documented / missing / a recorded exception, and each agent-wiki/ work record's issue references
	python3 scripts/check_docs.py report
check-pr-hygiene: ## CI: fail when a producer's commit message or PR body is empty, a placeholder, a subject with no body, or when AGENTS.md lost the mandate (issue #313)
	python3 scripts/check_pr_hygiene.py check
pr-hygiene-report: ## Show every producer the PR/commit-message guard reads, and its verdict
	python3 scripts/check_pr_hygiene.py report
# UNSUPPORTED=<file>: upstream engines with no skill are omitted from the trend
# offer (no image). Passing the decisions file tolerates ONLY the engines recorded
# there with a dated decision (issue #229); an engine with no skill and no decision
# is "new and unresolved" and FAILS, naming it. Without --unsupported every
# registry engine with no skill is an error, so the pinned fixture stays strict.
UNSUPPORTED ?=
skills-validate: ## Validate every engine skill against the trending-local-llms registry
	python3 scripts/engine_skills.py validate --registry "$(REGISTRY)" $(if $(UNSUPPORTED),--unsupported "$(UNSUPPORTED)",)
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
	# issue #204: the real published image's engine binary must answer its documented flags
	@mkdir -p "$(CI_HOME)"
	LLGENIE_PUBLISHED_PULLED=1 LLGENIE_TEST_ENGINE="$(ENGINE)" LLGENIE_TEST_ARCH="$(ARCH)" \
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
build-engines: ## Build every engine image for ARCH (cpu|cuda|rocm|vulkan) from the generated Dockerfiles
	@test -n "$(ARCH)" || { echo "Usage: make build-engines ARCH=cpu|cuda|rocm|vulkan [PUSH=1]"; exit 1; }
	@for e in $$(python3 scripts/engine_image.py matrix --json | python3 -c 'import json,sys;print(" ".join(r["engine"] for r in json.load(sys.stdin)["include"] if r["variant"]=="$(ARCH)"))'); do \
		$(MAKE) build-engine ENGINE=$$e ARCH=$(ARCH) $(if $(PUSH),PUSH=1,) || exit 1; done
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
# Token names only. docker copies the values from the environment; they stay off argv.
TEST_OPTS := --rm -u root -v "$(REPO)":/repo:rw -w /repo -e HOME=/root -e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN $(WORKTREE_MOUNT)
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
	-e HOME="$(CI_HOME)" -e LLGENIE_REGISTRY -e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN -e RUNTIME=docker $(WORKTREE_MOUNT)
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

publish-ci-images: ## CI job ci-images: build + push the test and OpenSpec images ONLY when their hash tag is not on GHCR yet. The AGENT image is NOT here: the default GITHUB_TOKEN is denied "Create organization package" for a brand-new package (the first llgenie/agent publish), so it goes out through publish-agent-image.yml with the owner PAT, deliberately and by hand
	python3 scripts/ci_images.py publish test openspec

publish-agent-image: ## Build + push ONLY the agent (Hermes) image to GHCR (linux/amd64: it builds Hermes at build time, which times out under arm64 emulation) when its hash tag is not there yet. The dedicated job for the Hermes container (issues #222/#238/#248); guarded to owner/collaborators.
	python3 scripts/ci_images.py publish agent

agent-image: ## The agent (Hermes) image: pull the published hash of its Dockerfile + install script (GHCR), else build it here
	python3 scripts/ci_images.py ensure agent

agent-image-pull: ## CI: pull the published agent image (hash of its Dockerfile + install script) as llgenie/agent:latest; fails if not published, never builds
	python3 scripts/ci_images.py pull agent

ci-image-refs: ## Print the GHCR refs of the CI images (test, openspec, agent) for the current Dockerfiles + lockfiles
	@python3 scripts/ci_images.py ref

test-variant-image: ## Build the CUDA toolkit + python variant-build image locally (the variant-build matrix is no longer a pipeline job; this reproduces it by hand)
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
	$(TEST_RUN) python -m pytest tests/test_llgenie_serve.py tests/test_hf_auth.py tests/test_hf_download_stall.py tests/test_hf_download_retry.py tests/test_lint_linefeeds.py tests/test_engine_bump_sync.py tests/test_engine_bump_rebase.py tests/test_check_openspec_tasks.py tests/test_remove_watchloop.py tests/test_ci_variant_matrix.py tests/test_serve_variant.py tests/test_ensure_user_path.py tests/test_engine_skills.py tests/test_engine_bump.py tests/test_engine_bump_pr_body.py tests/test_detect_server.py tests/test_model_engine_pick.py tests/test_trend_pick.py tests/test_registry_sync_trend.py tests/test_trend_list_matrix.py tests/test_registry_keys.py tests/test_engine_skill_gap.py tests/test_strata_download.py tests/test_macos_install.py tests/test_ci_images.py tests/test_mac_trend_pick.py tests/test_trend_list_acceptance.py tests/test_tensorfold_seamless.py tests/test_pick_matrix.py tests/test_pick_matrix_arch_perms.py tests/test_pick_full_registry.py tests/test_trending_quant_catalog.py tests/test_engine_supported_quants.py tests/test_quant_generator_edges.py tests/test_check_python_uv.py tests/test_engine_image_matrix.py tests/test_agents_worktree.py tests/test_agents_debt_analysis.py tests/test_bot_sync.py tests/test_wiring.py tests/test_agent_nerve.py tests/test_secret_output.py tests/test_kv_quant_bytes.py tests/test_queued_run_alarm.py tests/test_rename_llgenie_serve.py tests/test_fix_loop.py tests/test_fix_bot_sweep.py tests/test_issue_implementer.py tests/test_bot_time_budget.py tests/test_code_review.py tests/test_bot_pipeline_isolation.py tests/test_ci_concurrency.py tests/test_rebase_bot_sweep.py tests/test_bot_claims.py tests/test_check_docs.py tests/test_issue_refiner.py tests/test_dispatch_forms.py tests/test_workflow_guards.py tests/test_pr_hygiene.py -p no:cacheprovider -q -k 'not test_derive_reports_the_live_release_archives and not test_tensorfold_v1_0_5_release_is_native_archives and not test_tensorfold_release_archive_unpacks_and_runs'

# Live GitHub release reads. Linux only: the macOS runner cannot reach
# api.github.com, and TensorFold publishes no macos-x86_64 archive.
test-engine-bump-live: ## TensorFold v1.0.5 release archive: list, classify, checksum, run
	$(TEST_RUN) python -m pytest tests/test_engine_bump.py::test_derive_reports_the_live_release_archives tests/test_engine_bump.py::test_tensorfold_v1_0_5_release_is_native_archives tests/test_engine_bump.py::test_tensorfold_release_archive_unpacks_and_runs -p no:cacheprovider -q

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

test: ## Full fast suite (unit + install; containerized)
	$(TEST_RUN) python -m pytest tests/test_llgenie_serve.py tests/test_install.py tests/test_lint_linefeeds.py tests/test_kv_quant_bytes.py tests/test_rename_llgenie_serve.py tests/test_fix_loop.py tests/test_fix_bot_sweep.py -p no:cacheprovider -q

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
	$(MAKE) check-wiring
	$(MAKE) check-secret-output
	$(MAKE) check-docs
	$(MAKE) check-dispatch-forms
	$(MAKE) check-pr-hygiene

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
	$(MAKE) ci-install-dry-args
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
	@echo "  make render-trend-list-matrix    rewrite tests/fixtures/trend-list-matrix.json (the trending list per arch, vram, ram)"
	@echo "  make check-trend-list-matrix     CI: fail if that committed list differs from matrix() on the vendored registry"
	@echo "  make render-engine-skill-gap     rewrite data/engine-skill-gap.json (per-engine list + the models no engine can offer)"
	@echo "  make check-engine-skill-gap      CI gate: a registry engine with no skill and no dated decision in data/unsupported-engines.json, a stale decision, or a stale file"
	@echo "  make engine-skill-gap            show the gap: shipped / known-unsupported / NEW-unresolved engines"
	@echo "  make spawn-engine-skill-issues   open one tracking issue per NEW unskilled engine (the weekly sync runs this)"
	@echo "  make check-wiring                CI: fail when a test/script is wired to no make target, or only to one CI never runs (tests/fixtures/host-only-wiring.json records the deliberate ones)"
	@echo "  make check-secret-output         CI: fail when any file prints a secret's VALUE (an echo of a token variable), passes it on a command line (a value after -e), runs under a shell xtrace, dumps the environment around it, or commits a credential-shaped literal"
	@echo "  make wiring-report               show how every test/script is wired (target + whether CI runs it) and the host-only exceptions"
	@echo "  make issue-bot-dispatch          the issue-implementer dispatcher (issue #248): cap 3/day -> pick one labeled/ready issue -> claim -> write issue.md + branch"
	@echo "  make issue-bot-open-pr          open the draft-free PR linking ISSUE from BRANCH (never merges)"
	@echo "  make code-review-scan           the code-review bot: read the tree + the pipelines -> findings (REPO=; STATIC=1 skips the checks that read the GitHub API; no model spend, files nothing)"
	@echo "  make code-review-file           file ONE issue per NEW finding, capped per run (REPO=; CAP= per run, default 3; DRY=1 previews) — the bot's whole output is issues"
	@echo "  make implement-issue             the shared Hermes agent step: read issue.md + AGENTS.md, implement, run the gates, push nothing (NOUS_API_KEY from a secret)"
	@echo "  make hermes-smoke               one real Hermes call through the implementer alias (die in seconds)"
	@echo "  make agent-jev-preflight           report whether the JEV decision layer is available in the agent image (never blocks a run; NERVE_REQUIRE=1 verifies the image instead) — issue #238"
	@echo "  make check-docs                  CI: fail when a user-facing make target is not documented in README.md, a recorded exception is stale, or an agent-wiki/ work record references no issue"
	@echo "  make docs-report                 show every user-facing make target (documented / missing / recorded exception) and each work record's issue references"
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
