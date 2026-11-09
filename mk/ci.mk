ci-requeue-cancelled: ## Re-run the CI runs a bulk cancel killed, ONLY where the head sha has no other run (WINDOW=2h, DRY=1 previews; issue #843; a run GitHub answers "cannot be retried" is recorded skipped, never fatal, issue #2295)
	python3 scripts/ci_requeue.py run --repo $(GH_REPO) --window $(if $(WINDOW),$(WINDOW),2h) $(if $(DRY),--dry,)
ci-frozen-reaper: ## Cancel + re-run a run stuck in_progress past its threshold on an OPEN PR only (THRESHOLD=90m, DRY=1 previews; issue #1679)
	python3 scripts/ci_frozen_reaper.py run --repo $(GH_REPO) --threshold $(if $(THRESHOLD),$(THRESHOLD),90m) $(if $(DRY),--dry,)
auto-merge: ## Merge a PR ONLY when this run is green and the PR is conflict-free: state OPEN, mergeable MERGEABLE, mergeStateStatus CLEAN (no conflicts, not behind, not blocked), head pinned to HEAD_SHA, no do-not-merge label; then verify what it closed (PR= REPO= HEAD_SHA= from ci.yml; APPROVE=1 approves a green review-blocked PR with the other allowed identity; DRY=1 prints the decision)
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make auto-merge PR=<n> REPO=<owner/repo> [HEAD_SHA=<sha>] [APPROVE=1] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py auto-merge --repo "$(GH_REPO)" --pr $(PR) $(if $(HEAD_SHA),--head-sha $(HEAD_SHA),) $(if $(APPROVE),--approve-when-review-required,) $(if $(ACTOR),--actor $(ACTOR),) $(if $(DRY),--dry,)
# The auto-merge workflow is a `workflow_run`, so GitHub hands it a RUN ID, not a PR number: the run has
# to be resolved back to its PR before anything can be merged (issue #508). A fork `pull_request` run
# 404s on the runs endpoint and `gh api` prints the error BODY to stdout, so a value counts as a PR
# number only when it is digits; anything else falls through to the head-branch search, and nothing
# resolving fails loudly. The logic lives in scripts/resolve_run_pr.py and is tested in
# tests/test_resolve_run_pr.py — this target is the one code path the workflow runs.
# The auto-merge workflow is a `workflow_run`, so GitHub hands it a RUN ID, not a PR number: the run has
# to be resolved back to its PR before anything can be merged (issue #508). A fork `pull_request` run
# 404s on the runs endpoint and `gh api` prints the error BODY to stdout, so a value counts as a PR
# number only when it is digits; anything else falls through to the head-branch search, and nothing
# resolving fails loudly. The logic lives in scripts/resolve_run_pr.py and is tested in
# tests/test_resolve_run_pr.py — this target is the one code path the workflow runs.
auto-merge-resolve: ## Resolve the open PR a finished CI run belongs to (REPO= RUN_ID= HEAD_OWNER= HEAD_BRANCH=): writes `number=<n>` to $GITHUB_OUTPUT, treats a 404/error body as no answer and falls back to the fork head search, and fails loudly when nothing resolves (issue #508)
	@test -n "$(REPO)" && test -n "$(RUN_ID)" && test -n "$(HEAD_OWNER)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make auto-merge-resolve REPO=<owner/repo> RUN_ID=<id> HEAD_OWNER=<owner> HEAD_BRANCH=<branch>"; exit 1; }
	python3 scripts/resolve_run_pr.py resolve --repo "$(GH_REPO)" --run-id $(RUN_ID) --head-owner "$(HEAD_OWNER)" --head-branch "$(HEAD_BRANCH)"
auto-merge-channel: ## Route a `ci-scope`-fired sweep: `channel=auto-merge` when NO ci.yml run exists at HEAD_SHA (a docs-only head — this sweep decides), `channel=ci` when one does (REPO= HEAD_SHA=, writes `channel=` to $GITHUB_OUTPUT) (issue #1227)
	@test -n "$(REPO)" && test -n "$(HEAD_SHA)" || { echo "Usage: make auto-merge-channel REPO=<owner/repo> HEAD_SHA=<sha>"; exit 1; }
	python3 scripts/auto_merge_channel.py channel --repo "$(GH_REPO)" --head-sha $(HEAD_SHA)
# The fix-bot's sweep asks the SAME question with the opposite consequence (issue #629): a `CI` failure
# report can arrive after its PR already merged or closed, and then there is nothing to repair — so an
# empty answer is an answer (exit 0, `number=`), never a red run. The merge gate above must keep failing
# loudly, which is why this is a separate target over one resolver rather than a shared default.
# The fix-bot's sweep asks the SAME question with the opposite consequence (issue #629): a `CI` failure
# report can arrive after its PR already merged or closed, and then there is nothing to repair — so an
# empty answer is an answer (exit 0, `number=`), never a red run. The merge gate above must keep failing
# loudly, which is why this is a separate target over one resolver rather than a shared default.
fix-bot-resolve: ## Resolve the open PR a failed CI run belongs to for the fix-bot sweep (REPO= RUN_ID= HEAD_OWNER= HEAD_BRANCH=): writes `number=<n>` to $GITHUB_OUTPUT, and answers an EMPTY `number=` with exit 0 when the PR already merged or closed — nothing to repair, not a failure (issue #629)
	@test -n "$(REPO)" && test -n "$(RUN_ID)" && test -n "$(HEAD_OWNER)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make fix-bot-resolve REPO=<owner/repo> RUN_ID=<id> HEAD_OWNER=<owner> HEAD_BRANCH=<branch>"; exit 1; }
	python3 scripts/resolve_run_pr.py resolve --repo "$(GH_REPO)" --run-id $(RUN_ID) --head-owner "$(HEAD_OWNER)" --head-branch "$(HEAD_BRANCH)" --allow-none
auto-merge-recheck: ## Re-evaluate deferred PRs, and any concluded-green head no sweep ever decided — a cancelled or preempted sweep is retried without a push (REPO= [MAX=50] [DRY=1]) (issues #545, #2101)
	@test -n "$(REPO)" || { echo "Usage: make auto-merge-recheck REPO=<owner/repo> [MAX=50] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py recheck --repo "$(GH_REPO)" --max-prs $(if $(MAX),$(MAX),50) $(if $(DRY),--dry,)
auto-merge-explain: ## Print why a PR was (or was not) auto-merged: state, mergeability, merge state, review decision, author and the verdict — writes NOTHING (PR= REPO= [HEAD_SHA=])
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make auto-merge-explain PR=<n> REPO=<owner/repo> [HEAD_SHA=<sha>]"; exit 1; }
	python3 scripts/auto_merge.py explain --repo "$(GH_REPO)" --pr $(PR) $(if $(HEAD_SHA),--head-sha $(HEAD_SHA),)
check-merge-on-red: ## Fail when the PR head has a red check-run (failure, timed_out, or startup_failure), naming the run, the job and the first failing step (PR= REPO=) (issue #1386)
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make check-merge-on-red PR=<n> REPO=<owner/repo>"; exit 1; }
	python3 scripts/auto_merge.py red-check --repo "$(GH_REPO)" --pr $(PR)
alert-merged-red: ## Comment once on a recently merged PR whose head check-run is still red, naming the merge commit (REPO= [MAX=20] [DRY=1]) (issue #1386)
	@test -n "$(REPO)" || { echo "Usage: make alert-merged-red REPO=<owner/repo> [MAX=20] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py alert-merged-red --repo "$(GH_REPO)" --limit $(if $(MAX),$(MAX),20) $(if $(DRY),--dry,)
stacked-merge-detect: ## Report the PRs merged into a non-`main` base — a hand merge into a stacked base is a named report (author, head sha, check count), expected 0 (REPO= [MAX=20] [DRY=1]) (issue #963)
	@test -n "$(REPO)" || { echo "Usage: make stacked-merge-detect REPO=<owner/repo> [MAX=20] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py stacked-merged --repo "$(GH_REPO)" --limit $(if $(MAX),$(MAX),20) $(if $(DRY),--dry,)
verify-closure: ## Prove a merged PR closed what its body claims: prints every closing reference and its state, and fails naming an issue that is still OPEN (PR= REPO=)
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make verify-closure PR=<n> REPO=<owner/repo>"; exit 1; }
	python3 scripts/verify_closure.py verify --repo "$(GH_REPO)" --pr $(PR)
check-holds: ## CI: fail when an open PR carries `do-not-merge` with no resolving issue named anywhere (issue #948)
	python3 scripts/check_holds.py check
holds-report: ## Print every open PR carrying `do-not-merge` and the issue it names as the remedy (issue #948)
	python3 scripts/check_holds.py report
bind-proof: ## Bind a proof run's head_sha to the PR head it is cited for — fail unless the run proved the CURRENT head (PR= RUN=, issue #1293)
	@test -n "$(PR)" && test -n "$(RUN)" || { echo "Usage: make bind-proof PR=<n> RUN=<run-id>"; exit 1; }
	python3 scripts/bind_proof.py --pr $(PR) --run $(RUN)
check-main-ruleset: ## CI: fail when the main ruleset has no required_status_checks or misses a pinned context (the missing merge-block gate, issue #1400) — runs in the monitor workflow main-ruleset.yml; exits 2 when the ruleset cannot be read
	python3 scripts/check_main_ruleset.py check --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),)
main-ruleset-report: ## Print the main ruleset's measured state and the pinned required contexts, always exit 0 (issue #1400)
	python3 scripts/check_main_ruleset.py report --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),)
main-ruleset-apply: ## DRY by default: print the add-only required_status_checks PUT body; APPLY=1 with an admin token performs it (owner-admin-only, issue #1400)
	python3 scripts/check_main_ruleset.py apply --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),) $(if $(filter 1,$(APPLY)),--apply,)
check-arms: # internal alarm plumbing (rule 16 consumer) — stays out of the user-facing docs; its scheduled workflow arms.yml is the caller
	python3 scripts/check_arms.py check
arms-report: # internal alarm plumbing (rule 16 consumer) — stays out of the user-facing docs
	python3 scripts/check_arms.py report
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
	@python3 scripts/test_clean.py --runtime $(RUNTIME)
# internal CI seam (issue #1000): the `-m network` twin of test-unit, run by the admitted `ci-network` pipeline — every test the hermetic gate excludes by marker runs HERE, never silently skipped; not user-facing and no `##` help line on purpose (engine-matrix-pushed precedent)
# internal CI seam (issue #1000): the `-m network` twin of test-unit, run by the admitted `ci-network` pipeline — every test the hermetic gate excludes by marker runs HERE, never silently skipped; not user-facing and no `##` help line on purpose (engine-matrix-pushed precedent)
test-unit-network: bash-check
	$(MAKE) bash-check
	$(TEST_RUN) python scripts/unit_tests.py run --marker network
test-unit: ## Hermetic unit tests (containerized) — the suite is DISCOVERED, not enumerated: scripts/unit_tests.py selects every tests/test_*.py minus the dated exclusions in tests/fixtures/unit-suite.json (issue #393)
	$(TEST_RUN) python scripts/unit_tests.py run
# Live GitHub release reads. Linux only: the macOS runner cannot reach
# api.github.com, and TensorFold publishes no macos-x86_64 archive.
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
# ---- ci-<job>: ONE make target per CI pipeline job (issue #117) -------------
# pipeline.yml runs each as one job, on Linux AND on macOS (issue #120: the same
# file, no combined jobs). The commands are the same on both OSes. Every target
# that runs in a container needs the pulled llgenie/test (or llgenie/openspec) image:
# CI pulls the test image first with `make test-image-pull`; the openspec gate pulls-or-builds
# with `make openspec-image` (a fork PR cannot publish a NEW hash, issue #1673).
ci-lint: bash-check ## CI job lint: make lint + the zero-byte file gate
	$(MAKE) lint
	$(MAKE) check-empty-files
ci-unit: bash-check ## CI job unit: hermetic unit tests + registry / skill / Strata / engine-param / quant-catalog checks
	@python3 scripts/ci_unit.py
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
	$(ENGINE_TEST_RUN) sh -c 'mkdir -p ~/bin && touch ~/bin/not-ours && make uninstall && make test-uninstalled && test -e ~/bin/not-ours'
endif
ci-engines: bash-check ## Per-backend engine install for a host (BACKEND=cpu|cuda|rocm|vulkan|metal -> make test-install-published / each native-Metal engine + \"hi\" via scripts/ci_engines.py). No longer a CI stage: the engine install/serve test lives in the engine-build producer (#1027).
	@test -n "$(BACKEND)" || { echo "Usage: make ci-engines BACKEND=cpu|cuda|rocm|vulkan|metal"; exit 1; }
	python3 scripts/ci_engines.py $(BACKEND)
ci-slow-rows: ## CI: decide which heavy rows this run schedules — `linux / top-tier` runs on every non-PR event (push to main) and on a PR only with the `ci:slow` label (scripts/ci_slow_rows.py, issue #859)
	python3 scripts/ci_slow_rows.py decide --event "$$EVENT" --labels "$$LABELS"
ci-scope: ## CI: classify a diff into the CI classes and jobs it selects (scripts/ci_scope.py, issue #824) — the `scope` workflow step reaches the classifier through this target, never inline; BASE=<ref> diffs against it, ALL=1 keeps the full matrix (a push to main); DECISION=<path> also writes the machine-readable decision a finished run is held to (issue #1111)
	@test -n "$(BASE)" -o -n "$(ALL)" || { echo "Usage: make ci-scope BASE=<ref>|ALL=1 [DECISION=<path>]"; exit 1; }
	python3 scripts/ci_scope.py $(if $(ALL),--all,--base "$(BASE)") --decision-out "$${DECISION:-}"
ci-verdict: ## CI: hold a finished run to its published scope decision (scripts/ci_verdict.py, issue #1111) — a selected job that is skipped/cancelled/absent, or a run with no decision, is a FAILED verdict and a `ci-verdict` check-run on the head; a run a later run of the same workflow superseded is neutral, never success
	@test -n "$(RUN_ID)" -o -n "$(JOBS)" || { echo "Usage: make ci-verdict RUN_ID=<id> [REPO=<owner/repo>] [CHECK_RUN_OUT=<path>] | make ci-verdict JOBS=<path> [DECISION=<path>] [HEAD_SHA=<sha>]"; exit 2; }
	python3 scripts/ci_verdict.py --repo "$(GH_REPO)" --run-id "$(RUN_ID)" --jobs "$(JOBS)" --decision "$(DECISION)" --head-sha "$(HEAD_SHA)" --check-run-out "$(CHECK_RUN_OUT)"
verdict-roster: ## Print every workflow that can post a check-run at a PR head, the set `ci-verdict` judges, the difference, and the roster findings — a SUBSET check (`judged <= posters`), never equality (issue #2116)
	python3 scripts/verdict_roster.py report
ci-free-disk: ## CI: free runner disk for the large engine images (Linux runner: drop preinstalled SDKs; macOS runner: report only)
	@if [ "$$(uname -s)" = Linux ]; then sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL; \
	else echo "[ci-free-disk] $$(uname -s) runner: nothing to free"; fi
	@df -h /
