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
	@python3 scripts/build_server.py build --repo $(REPO) --server-root $(SERVER_ROOT) --stamp $(SERVER_BIN_STAMP)
# Explicit variant build (used by CI build-variants and by make install-<tree>-<backend>).
# Sets the env seams (LLAMA_SERVER_TREE / LLAMA_BACKEND / LLAMA_RAM_BYTES) and runs
# the SAME build_llama_server.sh, then stamps the binary path so `link` can
# symlink it. The tree override (LLAMA_SERVER_TREE) is authoritative, so CI can
# verify each tree+backend independently of the runner's card.
#   make build-variant TREE=prism BACKEND=cuda
# The build log is streamed (tee). Do not send it through `tail` or
# `2>/dev/null`: those hide the CUDA/Metal compile until the job ends.
# Explicit variant build (used by CI build-variants and by make install-<tree>-<backend>).
# Sets the env seams (LLAMA_SERVER_TREE / LLAMA_BACKEND / LLAMA_RAM_BYTES) and runs
# the SAME build_llama_server.sh, then stamps the binary path so `link` can
# symlink it. The tree override (LLAMA_SERVER_TREE) is authoritative, so CI can
# verify each tree+backend independently of the runner's card.
#   make build-variant TREE=prism BACKEND=cuda
# The build log is streamed (tee). Do not send it through `tail` or
# `2>/dev/null`: those hide the CUDA/Metal compile until the job ends.
build-variant:
	@python3 scripts/build_server.py build --repo $(REPO) --server-root $(SERVER_ROOT) --stamp $(SERVER_BIN_STAMP) --tree $(TREE) --backend $(BACKEND)
# Serve an already-built variant on its own port. Does not rebuild, does not
# relink ~/bin/llama-server, and does not stop whatever is already listening
# (the long-running server keeps its port). PORT empty picks a free
# 127.0.0.1 port. --n-gpu-layers is not passed. llama-server keeps its
# default and takes GPU or CPU, whichever it can.
#   make serve-variant TREE=prism BACKEND=cuda
#   make serve-variant TREE=prism BACKEND=cuda PORT=18080 MODEL=/path/to/model.gguf
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
# Stop the variant server this Makefile started. Does not touch any other port.
#   make stop-serve-variant TREE=prism BACKEND=cuda
stop-serve-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make stop-serve-variant TREE=prism BACKEND=cuda"; exit 1; }
	$(PY) scripts/serve_variant.py --tree "$(TREE)" --backend "$(BACKEND)" --stop
# ---- explicit variant install targets --------------------------------------
# One tree+backend. cpu/cuda run from the engine image (no host build); Metal is
# Apple-only and cannot run in a container, so it is the only native build.
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
engine-launchers: ## Pull this host's published engine images (default: llama.cpp + Prism; ENGINES=all|id,id; BUILD=1 builds unpublished ones), write ~/bin/llgenie-engine-<id> + the llama-server / prism-server shims
	python3 scripts/install_engine_launchers.py --bin "$(BIN)" $(if $(ARCH),--arch $(ARCH),) $(if $(BUILD),--build,) $(if $(ENGINES),--engines $(ENGINES),)
test-built-engine: ## After make install: every ~/bin/llgenie-engine-* start script must print its engine version via docker (Metal-only engines excluded)
	python3 scripts/install_engine_launchers.py --bin "$(BIN)" --test
test-engine-install: bash-check # Internal CI seam (issue #1027, deliberately internal like test-unit-network): after ENGINE's image was built + published in the engine-build producer, install + test-built-engine (the installed launcher must report the engine's version) + uninstall the just-published image — the producer-owned install leg. The product `llgenie --dry` step is deliberately NOT here: the producer is product-LESS (#1027 — the llgenie tool installs in pipeline.yml's ci-install, which already drives the product dry-run), so a producer that calls that product target can never satisfy it. Gating lives in the engine-build workflow (`inputs.push == 'true'`). On a GPU-less GitHub-hosted runner the cuda install-leg is NOT exercisable (no NVIDIA GPU / CDI to mount the host driver) and SKIPS with a documented reason instead of redding (issue #1240); a GPU host that lacks the CDI spec still fails loudly in install().
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine-install ENGINE=<id> ARCH=<variant>"; exit 1; }
	@reason="$$(python3 scripts/install_engine_launchers.py --install-leg-skip-reason --arch "$(ARCH)")"; \
	if [ -n "$$reason" ]; then echo "$$reason"; \
	else \
	  make engine-launchers ENGINES="$(ENGINE)" ARCH="$(ARCH)" && \
	  make test-built-engine && \
	  make ci-install-uninstall; \
	fi
# ---- engine skills (issue #98) ------------------------------------------
# One SKILL.md per inference server in skills/engines/<id>/. The skills are read
# ONLY by `make generate-engine-params` (and the inspection targets below:
# skills-validate, engine-list/plan/check). Every build target (install,
# build-variant, build-engine, run-engine, test-engine, CI) uses the GENERATED,
# committed files in containers/engines/ and runs with plain make: no LLM, no
# skills needed. tests/test_engine_skills.py builds from a repo copy without skills/.
# REGISTRY defaults to the pinned snapshot; pass the live URL to check drift:
#   make skills-validate REGISTRY=https://raw.githubusercontent.com/andyholst/trending-local-llms/master/data/models.json
# ---- trending registry (issue #105) ------------------------------------------
# data/models.json is a verbatim copy of trending-local-llms data/models.json:
# llgenie's trend pick reads it (no live fetch at run time). The registry-sync
# workflow runs `make sync-registry` weekly (cron 17 5 * * 1) and opens a PR when it changed.
sync-registry: ## Download trending-local-llms data/models.json (+ its README and data/model_contract.json, the contract the store must satisfy) into data/ (validated against that contract; written only when changed)
	python3 scripts/sync_registry.py sync
check-registry: ## Validate the vendored data/models.json against the vendored upstream contract, then fail when the sync LOST anything vs the committed copy — hermetic: the README-link probe replays the recorded answers in tests/fixtures/readme-link-answers.json, never the live Hub (issue #1178; LIVE=1 for the live probe on the ci-hf-live seam) (CI unit job)
	python3 scripts/sync_registry.py check $(if $(LIVE),--no-snapshot,)
	$(MAKE) check-registry-keys
check-registry-keys: ## Fail when the vendored registry dropped a key, model, measurement, t/s or counter vs the committed copy (additive only)
	python3 scripts/registry_keys.py
sync-quant-catalog: ## Regenerate data/trending-quant-catalog.json + its test fixture (the HF class table llgenie's pick reads) from the REAL registry + live Hub (read-only: lists quant plans + resolve links, never downloads a model; validates the newly-added links vs the prior generated table)
	python3 scripts/gen_trending_quant_catalog.py
check-quant-catalog: ## CI: fail when data/trending-quant-catalog.json differs from what the generator produces — hermetic: it replays the recorded Hub answers in tests/fixtures/quant-catalog-hub-snapshot.json, never the live Hub (issue #1178; LIVE=1 for the live comparison on the ci-hf-live seam)
	python3 scripts/gen_trending_quant_catalog.py --check $(if $(LIVE),,--snapshot)
render-trend-list-matrix: ## Rewrite tests/fixtures/trend-list-matrix.json from matrix(registry, vram, ram, arch) for the vendored registry, and record the Hub answers it read into tests/fixtures/hub-snapshot.json
	python3 scripts/trend_list_matrix.py
check-trend-list-matrix: ## CI: fail when the committed trend-list matrix differs from matrix() on the vendored registry — hermetic: it replays tests/fixtures/hub-snapshot.json (issue #1080; LIVE=1 for the live comparison)
	python3 scripts/trend_list_matrix.py --check $(if $(LIVE),--live,)
render-vram-scope-view: ## Rewrite tests/fixtures/vram-scope-view.json from scope_models(registry, DEFAULT_VRAM_RANGE) on the vendored registry — the committed default-band view (issue #227)
	python3 scripts/vram_scope_view.py
check-vram-scope-view: ## CI: fail when the committed default-band vram scope view differs from scope_models() on the vendored registry — pure function, no Hub, hermetic (issue #227)
	python3 scripts/vram_scope_view.py --check
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
sync-strata-models: ## Write data/strata_models.json from Strata's setup.py at the skill's pinned commit (the GGUF files Strata runs)
	python3 scripts/strata_models.py sync
check-strata-models: ## CI: fail when data/strata_models.json differs from Strata's setup.py at the pinned commit
	python3 scripts/strata_models.py check
engine-bump-rebase: ## Rebase every open chore/engine-bump-* PR onto the latest main (DRY=1 prints what it would do and pushes nothing)
	python3 scripts/engine_bump_rebase.py $(if $(DRY),--dry,)
engine-pins: ## Invent the engine install-string dependency pins (torch/litert/ziglang and every --index-url) into security-reports/engine-pins/ so the SBOM/Trivy pass covers them (issue #1282)
	python3 scripts/engine_pins.py inventory
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
check-engine-pins-published: ## CI: fail when an engine THIS CHANGE repins is not yet published in the registry — a pin bump may merge only once its exact image tag resolves a manifest (issue #1622; PRE-BASE resolves via scripts/base_ref, issue #925; no engine repinned => green and no network; ALL=1 sweeps the WHOLE committed fleet — every enabled cell's exact tag, red on any committed manifest unknown, issue #2190)
	python3 scripts/check_engine_pins_published.py check $(if $(BASE),--base "$(BASE)",) $(if $(ALL),--all,)
# Deliberately internal (no ## help line): the committed-set sweep's own routable hook is the
# @pytest.mark.network live test in tests/test_check_engine_pins_published.py (ci-network pipeline,
# issue #1000), so this target exists for a manual/all-new-backend call, never a CI gate that would
# red a normal PR on any temporarily-unpublished cell.
# Deliberately internal (no ## help line): the committed-set sweep's own routable hook is the
# @pytest.mark.network live test in tests/test_check_engine_pins_published.py (ci-network pipeline,
# issue #1000), so this target exists for a manual/all-new-backend call, never a CI gate that would
# red a normal PR on any temporarily-unpublished cell.
check-engine-pins-valid:
	python3 scripts/check_engine_pins_published.py check --all
engine-pins-published-report: ## Print the engines this change repins vs the base and their published-tag set (issue #1622)
	python3 scripts/check_engine_pins_published.py report $(if $(BASE),--base "$(BASE)",)
engine-build-pr-trigger: ## CI: dispatch engine-build push=true for every engine THIS change repins and await each verdict — the "will" arm of the pin-bump gate (issue #1633; PR_BASE/BASE resolves the base; no engine repinned => green, hermetic, nothing dispatched; --dry prints the plan)
	python3 scripts/engine_build_trigger.py check $(if $(BASE),--base "$(BASE)",) $(if $(BRANCH),--branch "$(BRANCH)",) $(if $(DRY),--dry,)
engine-build-pr-trigger-report: ## Print the engines this change repins and the dispatch plan (never dispatches; issue #1633)
	python3 scripts/engine_build_trigger.py report $(if $(BASE),--base "$(BASE)",)
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
test-published-engine: ## Issue #102: pull ENGINE's ARCH image AS PUBLISHED (no build, digest == :ARCH) and verify the engine BINARY answers -h/--version (issue #2319). The engine-build CI gate is binary-only — it never starts a server. The serving conformance test is HOST-only: `make test-engine-host ENGINE=<id> ARCH=<arch> [MODEL=...]` (or the explicit `--serve` tier `make test-engine-serve`), run manually by the llgenie-engine-improver with the smallest model that fits. `python3 scripts/engine_capability.py serve ENGINE ARCH` reports whether an arch may serve at all; the checkout's chat-testable decision is no longer part of the CI gate.
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make test-published-engine ENGINE=<id> ARCH=cpu|cuda|rocm|vulkan"; exit 1; }
	python3 scripts/engine_image.py pull-published "$(ENGINE)" $(ARCH_ARGS)
	$(MAKE) test-engine-image ENGINE=$(ENGINE) ARCH=$(ARCH)
	# issue #204: the real published image's engine binary must answer its flags (-h/--version, issue #2319).
	# It runs in the TEST IMAGE like every other test stage (issue #621): the runner's own python3 has
	# no pytest, so a bare `python3 -m pytest` here fails with "No module named pytest" — which is what
	# every test-published-* job did as soon as the published matrix started carrying rows again.
	@mkdir -p "$(CI_HOME)"
	$(call engine_test,LLGENIE_PUBLISHED_PULLED=1 LLGENIE_TEST_ENGINE="$(ENGINE)" LLGENIE_TEST_ARCH="$(ARCH)") \
		python3 -m pytest -q -p no:cacheprovider tests/test_published_engine_binary.py
	@$(CI_HOME_CLEAN)
	@echo "[published] $(ENGINE)/$(ARCH) binary verified (-h/--version); the serve conformance test is host-only (make test-engine-host, issue #2319)"
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
test-engine: ## Run ENGINE's image: the engine binary smoke (the DEFAULT, deterministic gate, never a 1200 s serving wait). Serve conformance is the explicit --serve tier: `make test-engine-serve` (issue #1717)
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine ENGINE=<id> [ARCH=cpu-portable]"; exit 1; }
	python3 scripts/engine_smoke.py "$(ENGINE)" $(ARCH_ARGS) --image
test-engine-serve: ## ENGINE's image: binary smoke AND the serving conformance tier (run the image, assert /v1/model+llm-local answers via the OpenAI SDK) — the --serve opt-in (issue #1717)
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine-serve ENGINE=<id> [ARCH=cpu-portable]"; exit 1; }
	python3 scripts/engine_smoke.py "$(ENGINE)" $(ARCH_ARGS) --image --serve
engine-smoke: ## Install ENGINE via its skill: the engine binary smoke (DEFAULT, deterministic; serving is the --serve tier). `--serve` adds the full serve+whether the skill launch line answers llm-local on a HOST entry point (issue #1717)
	@test -n "$(ENGINE)" || { echo "Usage: make engine-smoke ENGINE=<id> [BACKEND=cpu]"; exit 1; }
	python3 scripts/engine_smoke.py "$(ENGINE)" $(ENGINE_ARGS)
test-engine-host: ## Serve ONE engine's published image against a MODEL that fits host VRAM and the engine supports: parameterized as ENGINE=<id> ARCH=<arch> MODEL=<model> (issue #1322). Host use drives it ONE engine at a time (sequential, never parallel — GPU contention); the engine-build workflow's LAST step expands the supported (engine x arch) cells into a PARALLEL matrix keyed off the runner's own arch types. When MODEL is omitted the engine's smallest supported model is served. A GPU-less runner skips the GPU legs with a documented reason (#1240) and never reddens them. Never builds an image — only pulls the published one and runs it.
	@python3 scripts/engine_host_test.py $(if $(ENGINE),--engine $(ENGINE),) $(if $(ARCH),--arch $(ARCH),$(if $(HOST_ARCH),--arch $(HOST_ARCH),)) $(if $(MODEL),--model $(MODEL),) $(if $(PORT),--port $(PORT),) $(if $(TIMEOUT),--timeout $(TIMEOUT),)
engine-detect: ## Is ENGINE installed? Runs the skill's detect (ENGINE=<id> [BACKEND=])
	@test -n "$(ENGINE)" || { echo "Usage: make engine-detect ENGINE=<id> [BACKEND=cuda]"; exit 1; }
	python3 scripts/engine_skills.py detect "$(ENGINE)" $(ENGINE_ARGS)
# ---- helpers ------------------------------------------------------------
engine-capability-serve: ## Does ENGINE declare ARCH in engine-capabilities.json archs (issue #1214)? The serve-vs-flags decision (issue #1748): exit 0 -> the engine may serve on this arch (serve-leg/host-verify run), exit 1 -> binary-flags-only (never serve), exit 2 -> usage (ENGINE/ARCH). The workflow gates its serve legs on this target so every CI command is a make target, not an inline script (AGENTS.md).
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make engine-capability-serve ENGINE=<id> ARCH=<arch>"; exit 2; }
	@python3 scripts/engine_capability.py serve "$(ENGINE)" "$(ARCH)"
test-engine-stage: ## CI engine-image post-build test, ONE step for every image: TEST=serve -> binary flags (make test-engine-image) AND the engine binary smoke (make test-engine, the --image path's DEFAULT gate — never a serving readiness wait, issue #1717); TEST=detect -> binary flags only (make test-engine-image). The OpenAI-serving conformance tier is the explicit --serve opt-in (make test-engine-serve / the push serve-leg), and the workflow's serve legs run only for cells whose engine declares the arch (serve-vs-flags decision, issue #1748).
	@test -n "$(ENGINE)" -a -n "$(ARCH)" || { echo "Usage: make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect"; exit 1; }
	@case "$(TEST)" in \
	  serve)  $(MAKE) test-engine-image ENGINE="$(ENGINE)" ARCH="$(ARCH)" && \
	          $(MAKE) test-engine ENGINE="$(ENGINE)" ARCH="$(ARCH)" ;; \
	  detect) $(MAKE) test-engine-image ENGINE="$(ENGINE)" ARCH="$(ARCH)" ;; \
	  *) echo "[test-engine-stage] TEST must be serve or detect, got '$(TEST)'"; exit 1 ;; \
	esac
