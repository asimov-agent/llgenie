# mk/ci.mk — the CI job surface of the top Makefile (issue #800 → #2458).
#
# Moved BYTE-IDENTICAL from the top Makefile (issue #800 decomposition): `include mk/ci.mk` in the
# top Makefile brings them back. No recipe changed; only the file that declares each target moved.
#
# The adjacent non-ci blocks that sit BETWEEN these targets in the top Makefile (check-scanner-images,
# check-actions / actions-report / update-actions, check-renovate / renovate-report, the
# build-engine-% / run-engine-% / list pattern cluster and its UNSUPPORTED/PORT/ARCH_ARGS variables)
# are NOT ci-domain and stay in the top Makefile; the domain issues #2459-#2461 pick up their targets.

ci-requeue-cancelled: ## Re-run the CI runs a bulk cancel killed, ONLY where the head sha has no other run (WINDOW=2h, DRY=1 previews; issue #843; a run GitHub answers "cannot be retried" is recorded skipped, never fatal, issue #2295)
	python3 scripts/ci_requeue.py run --repo $(GH_REPO) --window $(if $(WINDOW),$(WINDOW),2h) $(if $(DRY),--dry,)

ci-frozen-reaper: ## Cancel + re-run a run stuck in_progress past its threshold on an OPEN PR only (THRESHOLD=90m, DRY=1 previews; issue #1679)
	python3 scripts/ci_frozen_reaper.py run --repo $(GH_REPO) --threshold $(if $(THRESHOLD),$(THRESHOLD),90m) $(if $(DRY),--dry,)

ci-scanner-images: ## CI job scanner-images: build and version-test every scanner image, publish on a push run only (policy in the script)
	python3 scripts/scanner_image.py ci

ci-image-refs: ## Print the GHCR refs of the CI images (test, openspec, agent) for the current Dockerfiles + lockfiles
	@python3 scripts/ci_images.py ref

ci-lint: bash-check ## CI job lint: make lint + the zero-byte file gate
	$(MAKE) lint
	$(MAKE) check-empty-files

ci-unit: bash-check ## CI job unit: hermetic unit tests + registry / skill / Strata / engine-param / quant-catalog checks
	$(MAKE) test-unit
	$(MAKE) skills-validate
	$(MAKE) check-registry
	$(MAKE) check-strata-models
	$(MAKE) check-quant-catalog
	$(MAKE) check-trend-list-matrix
	$(MAKE) check-vram-scope-view
	$(MAKE) skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json
	$(MAKE) check-engine-skill-gap
	$(MAKE) check-engine-params
	$(MAKE) check-engine-coverage
	$(MAKE) check-engine-source
	$(MAKE) check-engine-capabilities
	$(MAKE) check-engine-launchers
	$(MAKE) check-engine-pins-published
	$(MAKE) check-model-links
	$(MAKE) check-wiring
	$(MAKE) check-secret-output
	$(MAKE) check-docs
	$(MAKE) check-file-hygiene
	$(MAKE) check-architecture-census
	$(MAKE) check-dispatch-forms
	$(MAKE) check-pr-hygiene
	$(MAKE) check-report-hygiene
	$(MAKE) check-report-header
	$(MAKE) check-proc-gate
	$(MAKE) proc-gate-report
	$(MAKE) check-issue-bodies
	$(MAKE) check-skill-code-parity
	$(MAKE) check-pr-authors
	$(MAKE) check-pr-closing
	$(MAKE) check-pr-commit-checkboxes
	$(MAKE) check-pr-base
	$(MAKE) check-workflows
	$(MAKE) check-module-names
	$(MAKE) check-claim-reader
	$(MAKE) check-scanner-images
	$(MAKE) check-security-scan
	$(MAKE) check-security-issues
	$(MAKE) check-security-bumps
	$(MAKE) check-security-bot
	$(MAKE) check-actions
	$(MAKE) check-renovate
	$(MAKE) check-agent-skills
	$(MAKE) check-agent-profiles
	$(MAKE) check-agent-model
	$(MAKE) issue-bot-gates
	$(MAKE) issue-bot-gates-check
	$(MAKE) check-import-roots
	$(MAKE) check-package-layers
	$(MAKE) check-agent-profiles-ratchet

ci-agents-read: bash-check ## CI job agents-read: make test-agents-read (Python 3.12 venv -> AGENTS.md scan -> guard tests)
	$(MAKE) test-agents-read

ci-openspec: bash-check ## CI job openspec: validate the STRUCTURE of every active change and assert none has an unchecked task — a hardcoded change name let an invalid spec land (issue #156)
	$(MAKE) openspec-validate-all
	$(MAKE) openspec-tasks-check

ci-cpu-health: bash-check ## CI job cpu-health: Linux answers "hi" through the llama.cpp image; macOS never starts an engine image
	$(MAKE) test-health

ci-top-tier: bash-check ## CI job top-tier: same targets on both OSes (venv on macOS, test image on Linux)
	$(MAKE) test-top-tier-ci && $(MAKE) test-top-tier-serve-ci && $(MAKE) test-top-tier-cli-ci

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

ci-slow-rows: ## CI: decide which heavy rows this run schedules — `linux / top-tier` runs on every non-PR event (push to main) and on a PR only with the `ci:slow` label (scripts/ci_slow_rows.py, issue #859)
	python3 scripts/ci_slow_rows.py decide --event "$$EVENT" --labels "$$LABELS"

ci-scope: ## CI: classify a diff into the CI classes and jobs it selects (scripts/ci_scope.py, issue #824) — the `scope` workflow step reaches the classifier through this target, never inline; BASE=<ref> diffs against it, ALL=1 keeps the full matrix (a push to main); DECISION=<path> also writes the machine-readable decision a finished run is held to (issue #1111)
	@test -n "$(BASE)" -o -n "$(ALL)" || { echo "Usage: make ci-scope BASE=<ref>|ALL=1 [DECISION=<path>]"; exit 1; }
	python3 scripts/ci_scope.py $(if $(ALL),--all,--base "$(BASE)") --decision-out "$${DECISION:-}"

ci-verdict: ## CI: hold a finished run to its published scope decision (scripts/ci_verdict.py, issue #1111) — a selected job that is skipped/cancelled/absent, or a run with no decision, is a FAILED verdict and a `ci-verdict` check-run on the head; a run a later run of the same workflow superseded is neutral, never success
	@test -n "$(RUN_ID)" -o -n "$(JOBS)" || { echo "Usage: make ci-verdict RUN_ID=<id> [REPO=<owner/repo>] [CHECK_RUN_OUT=<path>] | make ci-verdict JOBS=<path> [DECISION=<path>] [HEAD_SHA=<sha>]"; exit 2; }
	python3 scripts/ci_verdict.py --repo "$(GH_REPO)" --run-id "$(RUN_ID)" --jobs "$(JOBS)" --decision "$(DECISION)" --head-sha "$(HEAD_SHA)" --check-run-out "$(CHECK_RUN_OUT)"

ci-free-disk: ## CI: free runner disk for the large engine images (Linux runner: drop preinstalled SDKs; macOS runner: report only)
	@if [ "$$(uname -s)" = Linux ]; then sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL; \
	else echo "[ci-free-disk] $$(uname -s) runner: nothing to free"; fi
	@df -h /
