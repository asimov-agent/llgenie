# llgenie install Makefile.
#
# `make install` does the WHOLE setup so you never touch the venv manually:
#   1. builds the Python 3.10 gguf-tooling venv (./tools/venv-install)
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

# Use the first bash on PATH so bash 5 (via brew on macOS) shadows the
# system bash 3.2. Linux/CI runners already have bash 5 in /bin/bash.
SHELL   := $(shell command -v bash 2>/dev/null || echo /bin/bash)
HOME    := $(shell printf '%s' "$$HOME")
BIN     := $(HOME)/bin
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
SERVER_ROOT := $(HOME)/repository/git
# Stamp file holding the path of the freshly-built llama-server binary (written
# by `build-server`). `link` symlinks ~/bin/llama-server from it, so build and
# link always agree on the binary.
SERVER_BIN_STAMP := $(HOME)/.llgenie/server.bin.path

.PHONY: all install venv-install link uninstall smoke list version help \
	openspec-image openspec-new openspec-validate openspec-status openspec-shell \
	test test-unit test-agents-e2e test-install test-install-ci test-install-host test-health download-test-model \
	test-image test-clean lint lint-fix loop loop-harness chained cron-install cron-uninstall cron-snapshot \
	build-server build-variant install-prism-cpu install-upstream-cpu \
	install-prism-cuda install-upstream-cuda install-prism-metal install-upstream-metal

# ---- container runtime (nerdctl preferred, docker fallback) --------------
RUNTIME ?= nerdctl
ifeq ($(shell command -v $(RUNTIME) >/dev/null 2>&1 && echo yes),)
RUNTIME = docker
endif
OS_IMG := llgenie/openspec:latest

all: install

# ---- full install: clone+build server + venv + launcher + smoke -----------
# `make install` does the WHOLE setup so you never touch the venv manually:
#   1. clones-or-pulls the RIGHT llama.cpp tree for the card (Prism <= 24 GB
#      VRAM, upstream > 24 GB) and builds it for the detected backend
#      (Metal / CUDA / CPU) — always to the latest commit (make build-server)
#   2. builds the Python 3.10 gguf-tooling venv (./tools/venv-install)
#   3. writes a runnable launcher `~/bin/llgenie` + symlinks it + the server
#      (make link)
#   4. verifies with a `--list` smoke run (make smoke)
#
# The host builds ONLY the right variant for its card (e.g. a 16 GB NVIDIA
# card -> prism+cuda, once). CI builds every variant in parallel (see
# .github/workflows/ci.yml build-variants).
install: build-server venv-install link smoke
	@echo
	@echo "Installed. Run '$(LAUNCHER)' (e.g. 'llgenie --list', 'llgenie qwen')."
	@echo "Symlink: $(BIN)/llgenie.py -> $(REPO)/scripts/llama_serve.py"
	@echo "llama-server: $(BIN)/llama-server -> $(LLAMA_SERVER_BIN)"

# ---- 1. build the gguf-tooling venv (Python 3.10 + gguf + numpy) --------
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
	# Symlink the freshly-built llama-server (path from SERVER_BIN_STAMP, written
	# by build-server) into ~/bin so llgenie.py resolves it on PATH.
	@SRV="$(shell cat $(SERVER_BIN_STAMP) 2>/dev/null)"; \
	if [ -n "$$SRV" ] && [ -x "$$SRV" ]; then \
		ln -sfn "$$SRV" "$(BIN)/llama-server"; \
		echo "==> Symlinked ~/bin/llama-server -> $$SRV"; \
	else \
		echo "WARN: no freshly-built llama-server (missing/stale $(SERVER_BIN_STAMP))." >&2; \
		echo "      Run 'make build-server' (or set SERVER_ROOT) so llgenie.py can serve." >&2; \
	fi
	@echo "==> Wrote $(LAUNCHER) (exec) and symlinked ~/bin/llgenie.py -> repo"

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
	SERVER_ROOT=$(SERVER_ROOT) $(REPO)/scripts/build_llama_server.sh "$$TREE" "$$BACKEND" 2>/dev/null | tail -n1 > /tmp/llgenie_srv_path; \
	SRV=$$(cat /tmp/llgenie_srv_path); \
	test -x "$$SRV" || { echo "ERROR: build-server did not produce a binary ($$SRV)"; exit 1; }; \
	mkdir -p $(dir $(SERVER_BIN_STAMP)); \
	printf '%s\n' "$$SRV" > $(SERVER_BIN_STAMP); \
	rm -f /tmp/llgenie_srv_path; \
	echo "==> server binary: $$SRV (stamped to $(SERVER_BIN_STAMP))"
# Explicit variant build (used by CI build-variants and by make install-<tree>-<backend>).
# Sets the env seams (LLAMA_SERVER_TREE / LLAMA_BACKEND / LLAMA_RAM_BYTES) and runs
# the SAME build_llama_server.sh, then stamps the binary path so `link` can
# symlink it. The tree override (LLAMA_SERVER_TREE) is authoritative, so CI can
# verify each tree+backend independently of the runner's card.
#   make build-variant TREE=prism BACKEND=cuda
build-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make build-variant TREE=prism BACKEND=cuda"; exit 1; }
	@TREE=$(TREE) BACKEND=$(BACKEND) \
		LLAMA_SERVER_TREE=$(TREE) LLAMA_BACKEND=$(BACKEND) \
		LLAMA_RAM_BYTES=17179869184 \
		SERVER_ROOT=$(SERVER_ROOT) $(REPO)/scripts/build_llama_server.sh "$(TREE)" "$(BACKEND)" 2>/dev/null | tail -n1 > /tmp/llgenie_srv_path
	@mkdir -p $(dir $(SERVER_BIN_STAMP))
	@SRV=$$(cat /tmp/llgenie_srv_path); \
		test -x "$$SRV" || { echo "ERROR: build-variant did not produce a binary ($$SRV)"; exit 1; }; \
		printf '%s\n' "$$SRV" > $(SERVER_BIN_STAMP); \
		rm -f /tmp/llgenie_srv_path
	@echo "==> stamped server binary: $$(cat $(SERVER_BIN_STAMP))"

# ---- explicit variant install targets (host: build the right one only) ----
# Each is a FULL install of ONE tree+backend: build-variant + venv + link + smoke.
# `make install` (no args) = build-server (auto-detect from the card) + venv + link + smoke.
install-prism-cpu: ## Build+install Prism llama.cpp (CPU)
	$(MAKE) build-variant TREE=prism BACKEND=cpu
	$(MAKE) venv-install link smoke
install-upstream-cpu: ## Build+install upstream llama.cpp (CPU)
	$(MAKE) build-variant TREE=upstream BACKEND=cpu
	$(MAKE) venv-install link smoke
install-prism-cuda: ## Build+install Prism llama.cpp (CUDA; needs nvcc)
	$(MAKE) build-variant TREE=prism BACKEND=cuda
	$(MAKE) venv-install link smoke
install-upstream-cuda: ## Build+install upstream llama.cpp (CUDA; needs nvcc)
	$(MAKE) build-variant TREE=upstream BACKEND=cuda
	$(MAKE) venv-install link smoke
install-prism-metal: ## Build+install Prism llama.cpp (Metal; macOS only)
	$(MAKE) build-variant TREE=prism BACKEND=metal
	$(MAKE) venv-install link smoke
install-upstream-metal: ## Build+install upstream llama.cpp (Metal; macOS only)
	$(MAKE) build-variant TREE=upstream BACKEND=metal
	$(MAKE) venv-install link smoke

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

openspec-image: ## Build the OpenSpec CLI container
	$(RUNTIME) build -t $(OS_IMG) openspec/
	@echo "OpenSpec image built: $(OS_IMG)"

OS_OPTS := --rm -u root -v "$(REPO)":/repo:rw -w /repo $(OS_IMG)

openspec-new: openspec-image ## openspec new change <NAME>
	@test -n "$(NAME)" || { echo "Usage: make openspec-new NAME=<kebab-name>"; exit 1; }
	$(RUNTIME) run $(OS_OPTS) openspec new change $(NAME)

openspec-validate: ## openspec validate <NAME>  (fail-closed gate used by the loop)
	@test -n "$(NAME)" || { echo "Usage: make openspec-validate NAME=<change>"; exit 1; }
	$(RUNTIME) run $(OS_OPTS) openspec validate $(NAME)

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
TEST_OPTS := --rm -u root -v "$(REPO)":/repo:rw -w /repo -e HOME=/root $(WORKTREE_MOUNT)
TEST_RUN := $(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)

# CUDA-toolkit (nvcc) + python image for the #84/#89 variant builds. The same
# image does all ubuntu-latest CPU + CUDA builds: builds use nvcc, and the
# 0.5B "hi" health check uses the bundled python + gguf/numpy/hf. (Metal builds
# run on macos-14 host toolchains — see the ci.yml jobs.)
VARIANT_IMG := gguf-tools/ci-variant:latest
VARIANT_RUN := $(RUNTIME) run $(VARIANT_OPTS) $(VARIANT_IMG)

test-image: ## Build the containerized test image (copies compiled requirements into context)
	@cp tools/requirements.txt tools/requirements-dev.txt containers/test/
	$(RUNTIME) build -t $(TEST_IMG) containers/test/
	@echo "Test image built: $(TEST_IMG)"

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
	$(TEST_RUN) python -m pytest tests/test_llama_ai.py tests/test_hf_download_stall.py tests/test_lint_linefeeds.py tests/test_watchloop_dispatch.py tests/test_check_openspec_tasks.py tests/test_install_watchloop_cron.py tests/test_watch_report.py -p no:cacheprovider -q

test-agents-e2e: ## REAL end-to-end agent tests (containerized) — runs ONLY *_e2e*.py files directly
	# issue #63 CI gate: exercises the REAL dispatcher spawn/kill/respawn against a fake
	# worker that does README issue-work, all within a minute. Only tests/*_e2e*.py run
	# (glob, so any future e2e file is picked up automatically).
	$(TEST_RUN) sh -c 'python -m pytest tests/*_e2e*.py -p no:cacheprovider -q'

test-agents-read: ## Guard: AGENTS.md must not match Hermes context-file threat patterns (fail-closed). Host-side: uses a Python >=3.11 that has hermes-agent installed (3rd-party PyPI dep, pinned ==0.19.0; the CI agents-read job installs it itself). Not containerized, to avoid bumping the 3.10 test image.
	@echo "==> test-agents-read: scanning AGENTS.md with the installed hermes-agent threat scanner"
	@AR=; for py in python3.12 python3.11; do \
	  if command -v $$py >/dev/null 2>&1 && $$py -c "import tools.threat_patterns" 2>/dev/null; then AR=$$py; break; fi; \
	done; \
	if [ -z "$$AR" ]; then \
	  echo "ERROR: no Python >=3.11 with hermes-agent installed found. Run 'pip install hermes-agent==0.19.0' into a Python >=3.11 interpreter (the CI agents-read job does this automatically)."; \
	  exit 1; \
	fi; \
	echo "  using $$AR"; \
	$$AR scripts/scan_agents_md.py AGENTS.md

test-install: ## Host install tests (containerized) — skips cleanly without artifacts
	$(TEST_RUN) python -m pytest tests/test_install.py -p no:cacheprovider -q

test-install-host: ## Verify the REAL host install (make install) — runs on the host where ~/bin/llgenie + ~/models exist
	# Runs tests/test_install.py with the gguf venv python on the HOST, so the
	# actual `make install` artifacts (~/bin/llgenie launcher, symlinks,
	# ~/bin/llama-server, ~/models) are asserted — not skipped. This is the
	# local/AGENTS.md proof that `make install` works.
	@echo "==> Verifying host install artifacts via tests/test_install.py"
	@$(PY) -m pytest tests/test_install.py -p no:cacheprovider -q

test-install-ci: ## REAL install tests inside the test container (NO SKIP): make install + seed model + assert artifacts, in ONE container
	# The install tests assert HOST install artifacts (~/bin/llgenie, ~/bin/llgenie.py,
	# llama-server on PATH, ~/models). They must not skip: so this target performs a REAL
	# `make install` (launcher + venv + symlinks) INSIDE the container, seeds the
	# lightweight model so --list/--dry have something, then runs the tests — all in a
	# SINGLE container session so the artifacts actually persist for pytest. Missing
	# prerequisites are a loud failure here, never a skip.
	@echo "==> test-install-ci: real make install + model seed + tests (no skips)"
	$(TEST_RUN) sh -c 'make install && python scripts/download_test_model.py && python -m pytest tests/test_install.py -p no:cacheprovider -q'

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

test-top-tier-serve-ci: ## Serve test inside the test container (CI/CPU): download lightweight, load, 'hi', RAM.
	$(TEST_RUN) python -m pytest tests/test_top_tier_serve.py -p no:cacheprovider -q -s -m acceptance

test-top-tier-cli-ci: ## REAL CLI dry-run in the test container: llgenie --download-top-tier [--family] --dry (no download/network writes)
	# Run the ACTUAL launcher entry point end-to-end with --dry, verifying the real
	# dispatch (main -> _main_download_top_tier), dynamic card readout, and the ranked
	# preview — no download and no server start. Deterministic card via LLAMA_RAM_BYTES.
	# The --family variant (issue #61) previews a known low-end family (1 provider)
	# the same way — a real HF family search, still no download.
	$(TEST_RUN) python -m pytest tests/test_top_tier_acceptance.py::test_cli_download_top_tier_dry_run_detailed tests/test_top_tier_acceptance.py::test_family_dry_run_known_lowend_one_provider -p no:cacheprovider -q -s -m acceptance

test-health: ## End-to-end CPU health check: ensure model, then tiny model answers 'hi' (containerized)
	$(TEST_RUN) sh -c 'python scripts/download_test_model.py && python -m pytest tests/test_health.py -p no:cacheprovider -q -s'

test: ## Full fast suite (unit + install; containerized)
	$(TEST_RUN) python -m pytest tests/test_llama_ai.py tests/test_install.py tests/test_lint_linefeeds.py -p no:cacheprovider -q

download-test-model: ## Fetch the lightweight (0.5B Q4 ~340MB) model into container ~/models/Qwen/8GB
	$(TEST_RUN) python scripts/download_test_model.py

lint: ## Linefeed lint: fail closed if any tracked text file lacks a trailing newline
	$(TEST_RUN) python scripts/lint_linefeeds.py

lint-fix: ## Append a missing trailing newline (containerized)
	$(TEST_RUN) python scripts/lint_linefeeds.py --fix

loop: loop-harness ## alias
loop-harness: ## Loop runner (host orchestration): image->download->lint->unit->install->health->test->openspec
	# The harness orchestrates the other stages by shelling out to `make`, so it
	# MUST run on the host (where make + nerdctl/docker live), NOT inside the
	# test container. It only needs python stdlib.
	@python3 scripts/loop_harness.py

# Run every verification step explicitly (Makefile-level chain, same order as
# loop-harness). Fails fast on the first failing step.
chained: test-unit test-agents-read test-install test-health test openspec-validate
	@echo "All chain steps completed."

uninstall: ## Remove the launcher + symlinks in ~/bin AND the cloned server trees (keeps venv AND repo source)
	# Removes just the installed artifacts the `link` target creates: the
	# ~/bin/llama-server launcher, the ~/bin/llama-serv.py symlink, and the
	# ~/bin/llama-server symlink. It MUST NOT delete repo source files
	# (scripts/llama_serve.py, scripts/hf_download.py) — those live in the
	# checkout/worktree and are tracked in git; deleting them breaks a
	# subsequent `make install`. Uninstall also removes the cloned llama.cpp
	# server trees (issue #89: CI variant jobs clone these into ~/repository/git
	# and must not pollute the workspace).
	@rm -f "$(LAUNCHER)" "$(BIN)/llama-serv.py" "$(BIN)/llama-server"
	@rm -rf "$(SERVER_ROOT)/prism-llama.cpp" "$(SERVER_ROOT)/llama.cpp"
	@echo "Removed $(LAUNCHER), $(BIN)/llama-serv.py, $(BIN)/llama-server, $(SERVER_ROOT)/prism-llama.cpp, $(SERVER_ROOT)/llama.cpp"
	@echo "(venv kept at $(VENV) and repo source untouched; 'make -C tools clean' to drop requirements.txt)"

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

help:
	@echo "Targets:" \
		"install (venv+launcher+symlink+smoke), venv-install, link, smoke,"
	@echo "         test-unit, test-agents-e2e (real agent e2e), test-install, test-health (endpoint answers 'hi'), test,"
	@echo "         download-test-model, openspec-validate, openspec-new/status,"
	@echo "         loop (chained runner), loop-harness, chained, uninstall,"
	@echo "         cron-install, cron-uninstall, cron-snapshot (watch-loop host crontab),"
	@echo "         watch-report (human-readable watch-loop status report)"
	@echo
	@echo "Server build variants (issue #84):"
	@echo "  make install                 auto-detect tree+backend for this card, clone-or-pull + build + link"
	@echo "  make build-variant TREE=prism|upstream BACKEND=cpu|cuda|metal   build one variant in isolation"
	@echo "  make install-prism-cpu|upstream-cpu|prism-cuda|upstream-cuda|prism-metal|upstream-metal"
	@echo "                               full install of ONE tree+backend (build + venv + link + smoke)"
	@echo
	@echo "Env seams (override detection):"
	@echo "  LLAMA_SERVER_TREE=prism|upstream   force the llama.cpp tree (else card RAM: <=24GB prism, >24GB upstream)"
	@echo "  LLAMA_BACKEND=cpu|cuda|metal       force the backend (else hardware: Metal/CUDA/CPU)"
	@echo "  LLAMA_RAM_BYTES=<bytes>            force the card RAM used by the tree decision"
	@echo "  SERVER_ROOT=<dir>                  where llama.cpp trees are cloned (default ~/repository/git)"
