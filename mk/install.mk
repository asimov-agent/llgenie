# mk/install.mk — the host-install domain of the top Makefile (issue #800 → #2461).
#
# Moved BYTE-IDENTICAL from the top Makefile (issue #800 decomposition): `include mk/install.mk`
# in the top Makefile brings them back. No recipe changed; only the file that declares each
# target moved. Each block spans from its target line through the first blank line OR the next
# target header (ifeq depth tracked), so neighbours with no blank line between them never bleed in.

install: bash-check venv-install engine-launchers link test-built-engine smoke provision-agent-profiles
	@echo
	@echo "Installed (published engine images for this host's backend pulled + start scripts written + version-tested)."
	@echo "Run '$(LAUNCHER)' (e.g. 'llgenie --list', 'llgenie qwen'), or e.g. '$(BIN)/llgenie-engine-llama-cpp ~/models/m.gguf'."
	@echo "Tips: 'make run-engine ENGINE=<id> MODEL=<m>' / 'make stop-engine ...' run/stop an engine image."

venv-install:
	@echo "==> Building gguf venv at $(VENV)"
	$(MAKE) -C tools venv-install

link:
	@mkdir -p "$(BIN)"
	@printf '#!/usr/bin/env bash\n# llgenie launcher -> runs %s with the %s venv.\n# Prepend ~/bin to PATH so the llama-server symlink there resolves in any shell.\nexport PATH="$(BIN):$$PATH"\nexec "%s" "%s" "$$@"\n' \
		"$(REPO)/scripts/llgenie_serve.py" "$(VENV)" "$(PY)" "$(REPO)/scripts/llgenie_serve.py" > "$(LAUNCHER)"
	@chmod +x "$(LAUNCHER)"
	@ln -sfn "$(REPO)/scripts/llgenie_serve.py" "$(BIN)/llgenie.py"
	# ~/bin/llama-server is the container shim written by engine-launchers (no native build).
	@echo "==> Wrote $(LAUNCHER) (exec) and symlinked ~/bin/llgenie.py -> repo"
	@$(PY) scripts/ensure_user_path.py

smoke:
	@echo "==> Smoke test: $(LAUNCHER) --list"
	- if $(LAUNCHER) --list; then echo "==> OK: launcher runs and found models."; else echo "==> Launcher installed and runs. (No .gguf under ~/models yet — install succeeds; use 'llgenie --download-top-tier' to fetch trending top-tier models, or drop a .gguf into ~/models and run 'make list'.)"; fi

test-install: ## Host install tests (containerized) — skips cleanly without artifacts
	$(TEST_RUN) python -m pytest tests/test_install.py -p no:cacheprovider -q

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

hf-cli-install: ## Provision the `hf` downloader the engine-build tiny-test-model step uses (issue #2380): install the EXACT huggingface_hub version pinned in tools/requirements.in — never a floating `>=`, which drifted to a 2.x whose `cli` extra was removed (AGENTS.md: every CI command is a make target).
	@spec="$$(grep '^huggingface_hub==[0-9]' tools/requirements.in || true)"; \
	test -n "$$spec" || { echo "[hf-cli-install] tools/requirements.in pins no huggingface_hub==<version>"; exit 1; }; \
	echo "[hf-cli-install] uv tool install $$spec (from tools/requirements.in)"; \
	uv tool install "$$spec"
