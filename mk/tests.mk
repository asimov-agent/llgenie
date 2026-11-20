# mk/tests.mk — test-suite-domain targets split out of the top Makefile (issue #2677).
# Target names, prerequisite lines, guard comments and recipes are byte-identical;
# shared variables stay in the top Makefile; .PHONY entries stay in the top file
# (bots.mk precedent). PY312/AGENTS_READ_* move with their targets because
# agents-read-venv expands $(AGENTS_READ_STAMP) at parse time.
test-env: ## The Python 3.11 test environment: Linux pulls llgenie/test (python:3.11-slim); macOS builds the 3.11 gguf venv + dev deps and puts uv on PATH (no container)
ifeq ($(HOST_OS),Darwin)
	$(MAKE) -C tools venv-dev-install
	@command -v uv >/dev/null || brew install uv
	@command -v uv >/dev/null
else
	python3 scripts/ci_images.py pull test
endif

test-clean: ## Remove left-over/stopped orphaned containers of the test image (interrupted/failed runs)
	@python3 scripts/test_clean.py --runtime "$(RUNTIME)" --test-img "$(TEST_IMG)"

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

test-board-ownership-host: ## HOST-ONLY proof of #2353 AC3 (runs the real hermes CLI against a throwaway HERMES_KANBAN_DB; recorded host-only in unit-suite.json + host-only-wiring.json)
	@$(PY) -m pytest tests/test_kanban_single_card_reassign.py -p no:cacheprovider -q

test-recall-step: ## Host proof of the orchestrator STEP 2 recall fallback (issue #2186): asserts the pinned 9177 recall returns `results` and that the wrong default port 8888 fails while 9177/health succeeds. Needs the live hindsight daemon on 127.0.0.1:9177 (HINDSIGHT_API_PORT in ~/.hindsight/profiles/hermes.env), which no CI runner has, so it is kept OUT of the hermetic gate (tests/fixtures/unit-suite.json) and run on the tick host
	@$(PY) -m pytest tests/test_procedure_recall_step.py -p no:cacheprovider -q

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

test: ## Full fast suite (unit + install; hermetic files in the container, install artifacts on the host)
	# tests/test_install.py asserts the REAL ~/bin/llgenie + ~/models, which a `--rm` container with
	# HOME=/root can never hold: in the container those six assertions can only ever fail (#317). The
	# hermetic files run here — the `fast` group the roster records (issue #403), so this recipe
	# names no test file; the install assertions run on the host, where the artifacts live.
	$(TEST_RUN) python scripts/unit_tests.py run --group fast
	$(MAKE) test-install-host

download-test-model: ## Fetch the lightweight (0.5B Q4 ~340MB) health model into the shared stage HOME: $(CI_HOME)/models/Qwen/8GB (issue #356: survives the container; test-health reuses it)
	@mkdir -p "$(CI_HOME)"
	$(MODEL_CACHE_RUN) python scripts/download_test_model.py
