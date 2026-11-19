# llgenie install Makefile.

include mk/gates.mk  # gates domain (issue #2457)
include mk/engines.mk  # engine domain (issue #2456)
include mk/security.mk
include mk/install.mk  # install domain (issue #2461)
include mk/ci.mk
include mk/bots.mk  # bots domain (issue #2460)
include mk/tests.mk  # test-suite domain (issue #2677)
include mk/images.mk  # images domain (issue #2678)
include mk/agents.mk  # agents domain (issue #2676)
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
	test test-unit test-agents-read agents-read-venv test-install test-install-ci test-install-host test-install-trend test-health test-health-host test-recall-step test-board-ownership-host download-test-model \
	test-image test-image-pull openspec-image-pull publish-ci-images publish-agent-image agent-image-push-check agent-image agent-image-pull agent-image-profiles-check ci-image-refs test-clean lint lint-fix loop loop-harness chained sweep-concurrency-report \
	build-server published-engine-pull published-engine-binary build-variant serve-variant test-serve-variant stop-serve-variant install-prism-cpu install-upstream-cpu \
	install-prism-cuda install-upstream-cuda install-prism-metal install-upstream-metal \
	sync-registry check-registry skills-validate engine-list engine-hardware engine-plan engine-check engine-install engine-detect engine-smoke test-engine test-engine-serve ci-engine-images build-engine-base build-engines generate-build-engine-params test-engine-image push-engine test-published-engine check-engine-cache-namespace test-install-published engine-launchers test-built-engine test-uninstalled engine-capability-serve registry-cache-orphans registry-cache-gc \
		sync-quant-catalog check-quant-catalog render-trend-list-matrix check-trend-list-matrix check-trend-list-fresh trend-staleness-issue render-engine-skill-gap check-engine-skill-gap \
	render-vram-scope-view check-vram-scope-view \
	engine-gate-report engine-skill-gap engine-skill-gap-md spawn-engine-skill-issues post-merge-live-check engine-skill-scaffold registry-change-report sync-change-issue registry-review-brief registry-sync-review registry-review-publish sync-strata-models check-strata-models check-strata-models-live check-wiring wiring-report check-secret-output secret-output-report \
	secret-scan secret-scan-history secret-scan-self-test \
	queued-alarm check-zero-job-pending stale-branch-cleanup issue-cleaner-scan issue-cleaner-apply worktree-report worktree-prune fix-loop fix-loop-image fix-bot-sweep fix-bot-report lane-reconcile-guard agent-image-ref issue-bot-dispatch issue-bot-open-pr issue-bot-image ci-frozen-reaper issue-bot-pr-body-check agent-repo-ownership \
	issue-bot-triage issue-bot-changed issue-bot-verdict issue-bot-gates issue-bot-gates-check lane-preflight implement-issue hermes-smoke agent-jev-preflight jev-preflight-required nerve-profile-check code-review-scan code-review-file rebase-bot-sweep rebase-bot rebase-bot-abort \
	memory-install memory-bootstrap memory-verify memory-check memory-render memory-status \
	engine-params-review-brief engine-params-review engine-params-review-apply \
	architecture-bot-brief architecture-bot-doc architecture-bot-publish architecture-bot check-arms arms-report \
	scrub-log \
	check-pr-heads pr-heads-report bot-verdict bot-verdict-read \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report changes-resolve check-pr-hygiene check-pr-agents-line check-pr-commit-checkboxes check-pr-sync-line pr-hygiene-report check-report-hygiene report-hygiene-report check-module-names check-claim-reader check-issue-bodies issue-bodies-report check-agent-access agent-access-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows check-workflows-shellcheck workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report security-scan security-scan-all security-scan-images security-scan-image security-scan-published security-scan-fixture security-verdict security-issues security-issues-reconcile security-issues-plan check-security-issues security-bot security-bot-pick check-security-bot sbom check-security-scan check-gitleaks-pin engine-pins scanner-image test-scanner-image scanner-digests pin-scanner-image-digests scanner-ref semgrep-rules-refresh scanner-freshness publish-scanner-images ci-security-images security-images-ensure check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report check-issue-bodies issue-bodies-report check-agent-access agent-access-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows check-workflows-shellcheck workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report scanner-image test-scanner-image scanner-digests pin-scanner-image-digests scanner-ref semgrep-rules-refresh publish-scanner-images ci-security-images security-images-ensure check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows check-workflows-shellcheck workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-actions actions-report update-actions \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows check-workflows-shellcheck workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-renovate renovate-report \
	arm-auto-merge arm-auto-merge-report check-agent-model-catalog \
	security-bumps security-bumps-plan check-security-bumps \
	agent-shell-keys-check \
	agent-fetch search-smoke require-env web-coverage issue-evidence \
	engine-bump-rebase generate-engine-params check-engine-params check-engine-coverage engine-coverage-report check-engine-source engine-source-report check-engine-capabilities engine-capabilities-report check-engine-launchers engine-launchers-report check-engine-pins-published check-engine-pins-valid engine-pins-published-report engine-build-pr-trigger engine-build-pr-trigger-report check-model-links model-links-report build-engine run-engine stop-engine list-engine-images engine-build-matrix test-engine-host ci-lint ci-unit ci-agents-read \
	ci-openspec ci-cpu-health ci-top-tier ci-install ci-install-dry-args ci-free-disk ci-slow-rows ci-scope ci-verdict verdict-roster test-engine-stage hf-cli-install bot-sync-main bot-sync-branch ci-wait-engine-images \
	ci-install-dry ci-install-run ci-install-uninstall test-env test-top-tier test-top-tier-ci test-top-tier-cli-ci test-top-tier-serve test-top-tier-serve-ci \
	check-agent-model model-pin-report check-agent-skills agent-skills-report test-agent-skills-live hermes-skills-register \
	sync-agent-profile check-agent-profiles agent-profiles-report tester-fold-live provision-agent-profiles \
	apply-hermes-base-config seed-hermes-profile-env \
	test-hub-live test-strata-live test-engine-bump-live test-native-engines test-native-engine-light test-variant-image \
	bash-check engine-bump engine-bump-daily engine-bump-plan engine-derive generate-requirements openspec-tasks-check check-registry-keys ci-engines all-pipelines-sweep bots-restore-health audit-ticks audit-ticks-notes audit-ticks-post targets-coverage

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

# ---- 1. build the gguf-tooling venv (Python 3.11 + gguf + numpy) --------

# ---- 2+3. launcher wrapper + symlink into ~/bin -------------------------

# ---- 4. smoke: confirm the launcher can list models ---------------------

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
serve-variant:
	@test -n "$(TREE)" -a -n "$(BACKEND)" || { echo "Usage: make serve-variant TREE=prism BACKEND=cuda [PORT=] [MODEL=]"; exit 1; }
	$(PY) scripts/serve_variant.py --tree "$(TREE)" --backend "$(BACKEND)" \
		--port "$(if $(PORT),$(PORT),0)" \
		$(if $(MODEL),--model "$(MODEL)",) \
		--server-root "$(SERVER_ROOT)"

# POST "hi" to the variant server, then stop only that process.
#   make test-serve-variant TREE=prism BACKEND=cuda
export LLGENIE_REGISTRY ?= ghcr.io/asimov-agent
REGISTRY ?= tests/fixtures/trending-models.json
ENGINE_ARGS = $(if $(BACKEND),--backend $(BACKEND),)
# ---- trending registry (issue #105) ------------------------------------------
# data/models.json is a verbatim copy of trending-local-llms data/models.json:
# llgenie's trend pick reads it (no live fetch at run time). The registry-sync
# workflow runs `make sync-registry` weekly (cron 17 5 * * 1) and opens a PR when it changed.
REGISTRY_REVIEW_BRIEF ?= registry-review-in.md
REGISTRY_REVIEW_OUT ?= registry-review.md

# ---- the model chain the bots run (issue #405, chain home issue #2929) ------
# The bots no longer name a model. `agents/hermes-base-config.yaml` declares the chain ONCE
# (Nous free models first — `nous-longcat` primary — the other free models as the ordered
# fallbacks, `deepseek/deepseek-v4-flash-0731` LAST), `scripts/apply_hermes_base_config.py`
# merges its owned keys into the agent image's global Hermes home AND every llgenie lane
# profile's config.yaml, and each bot call runs as its lane profile (`hermes -p llgenie-<lane>`)
# which loads the chain from its own config. `scripts/agent_model_pin.py` referees the chain,
# the budgets and the wiring: no `-m` bot flag may return to this tree.
.PHONY: bot-preflight
.PHONY: bot-stamp-body
.PHONY: bot-close-reasons-report
.PHONY: bot-body-write
.PHONY: check-import-roots
.PHONY: check-package-layers
.PHONY: check-agent-profiles-ratchet

.PHONY: provision-agent-profiles apply-hermes-base-config seed-hermes-profile-env


.PHONY: skill-parity check-skill-code-parity


.PHONY: profile-drift-alarm


.PHONY: check-tick-prompt


.PHONY: check-cron-drift


.PHONY: verify-lane-contract


.PHONY: profile-drift
require-env: ## Refuse to start when a credential a leg needs is missing (KEYS="NOUS_API_KEY ..."; name-only, exit 2)
	@test -n "$(KEYS)" || { echo "Usage: make require-env KEYS=\"NOUS_API_KEY [TYPESAFE_API_KEY]\""; exit 1; }
	python3 scripts/require_env.py $(KEYS)

# `$(call …)` splits its arguments on COMMAS IN THE UNEXPANDED TEXT, so a literal `-s a,b` inside
# the call keeps only `-s a`: the rest is dropped, the shell sees an unclosed quote, and the leg dies
# with `unexpected EOF while looking for matching '` before the agent starts (issue #641, measured on
# #602/#605 staying DIRTY). The skills therefore come from a variable — no comma in the call text —
# and `make -n rebase-bot-agent` is the proof.
REBASE_BOT_SKILLS := rebase-conflict,bot-unattended


# The documentation review of an engine's DERIVED build parameters (issue #583). The bump proves the
# params COMPILE; this leg checks them against the engine's own docs for the arch being built. The host
# stays the writer: the agent may only propose a `-D` flag whose evidence it quotes from the upstream
# tree at the pin, and the apply step drops anything it cannot find there.
.PHONY: orchestrator-tick orchestrator-tick-pending orchestrator-tick-report
# The chain lives in agents/hermes-base-config.yaml; profiles own the model (issue #2929).
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

# ---- the reach, DEPLOYED: what a bot run actually depends on (issue #380) ------------------
# #362 built the leg and the smoke; no bot leg called either, so the capability was unreachable from
# a run and nothing said which URLs the bots need. `scripts/web_evidence.py` closes that half:
# `web-coverage` reports each URL's HTTP status (no model, no key — a 404 is dead for a bot too), and
# `issue-evidence` pre-fetches the URLs an issue names with the REAL `agent-fetch` leg, so the agent
# reviews against fetched text instead of guessing. `issue-refiner` is the first consumer.


# The code-review bot (issue #269): it reads the TREE and the PIPELINES and files what is
# actually wrong. Its whole output is issues — analysis, never implementation (AGENTS.md,
# #231) — so it never edits a file, never opens a PR and never merges; each issue carries the
# evidence the finding was derived from, so a reviewer can check the claim without re-deriving
# it. `scan` is free (no model, no API writes); `file` writes issues and dedups by a marker in
# the body, so a re-run of an unchanged tree files nothing.

# ---- the architecture bot (issue #449) ---------------------------------------
# `docs/ARCHITECTURE.md` is the map of the shipped path, and it ages the moment the tree moves.
# This bot re-derives it every 6 hours: a deterministic brief from real `git` state (no model),
# ONE Hermes leg that may write only that doc, and a deterministic publish that files ONE issue
# and ONE linked PR. A run with no drift files nothing, and no run ever merges.
DOC ?= docs/ARCHITECTURE.md
ARCH_BRIEF ?= architecture-brief.md
STAMP ?= $(shell date -u +%Y%m%dT%H%M)


# ---- the acceptance-tick audit (issue #2631, follow-up #2288) -----------------
# #2288 made NEW acceptance ticks honest; this tool re-measures the WHOLE closed-issue
# corpus and resolves the recorded-stale ticks append-only: supersession notes, never
# rewrites. `audit` exits 0 only when zero unsuperseded stale ticks remain.
AUDIT_OUT ?= audit-out


# The run-failure reactor (issue #286): a bot that reacts to a FAILED CI run — any run, not just
# a PR check — and routes it to a remedy. The route decision lives in scripts/run_failure_reactor.py
# (stdlib only, no LLM), never in a job `if:` that can silently skip (issue #107). Route A: a
# pushable same-repo PR -> claim it (scripts/bot_claims.py, #279/#285) and dispatch the EXISTING
# fix-bot. Route B: no pushable PR -> file ONE marker-deduped issue labelled `agent:implement`.
# It never repairs/commits/pushes/merges in the file-issue path; a run it cannot diagnose is loud.
# The identity `gh workflow run` dispatches with is the repository-scoped `GH_TOKEN` the workflow's
# job already sets (`${{ github.token }}`, issue #412): fix-bot's guard now ADMITS the repository bot
# on a `workflow_dispatch` (#1571), and the owner PAT lacks the dispatch scope (#2091). The token is
# taken by NAME from the environment only — never on argv. Locally it comes from whatever GH_TOKEN
# the shell already holds.

all-pipelines-sweep: ## CI: umbrella sweep — enumerate the tree's workflows, dispatch + await every dispatchable one (except itself), report every disabled one and the `N ok · M failed · K disabled` summary (issue #1102; REPO= owner/repo, REF= the branch to dispatch at)
	python3 scripts/all_pipelines.py sweep --repo "$(if $(REPO),$(REPO),$(GH_REPO))" --ref "$(if $(REF),$(REF),main)"
targets-coverage: ## Print every Makefile target with the callers found (workflow step, script reference, or none), marking `_`-prefixed targets internal, so "which targets does nothing run" is a measurement (issue #1102)
	python3 scripts/targets_coverage.py
worktree-report: ## Report every worktree with its branch, merged-into-main, open PR, dirty state, ahead/behind and uncommitted paths; a workspace lane prints the primary checkout's parked branch so the spawn defect is visible before it seeds the next worktree; mutates nothing and deletes nothing (issues #794, #845); SLUG= picks the repo gh reads, BASE= the base ref
	python3 scripts/worktree_report.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main)
worktree-base: ## Resolve the base a worktree MUST be cut from — `refs/remotes/origin/main`, fetched first, NEVER the primary checkout's HEAD (issue #845); ADD=1 PATH= DIR= BRANCH= passes the resolved base to `git worktree add` so the dispatch seam cuts from origin/main regardless of what the primary checkout is parked on
	@python3 scripts/worktree_base.py $(if $(ADD),add --path "$(PATH)" --branch "$(BRANCH)",resolve)
worktree-prune: ## Remove the worktrees and branches whose work landed on the base — proven by the PR's merge commit OR by ancestry, and held back by any OPEN PR or OPEN issue the branch names (issues #431, #2262); DRY=1 prints the plan, BASE= picks the base ref, SLUG= the owner/name gh reads; an UNATTENDED run — CI, BOT, or the dispatcher's HERMES_KANBAN_* — is REFUSED unless CONFIRM=1 (issue #794)
	@python3 scripts/worktree_prune_guard.py
	python3 scripts/worktree_prune.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main) $(if $(DRY),--dry,)
stale-branch-cleanup: ## Delete non-main branches older than 3 days with no open PR and fully delivered commits (issue #1344); APPLY=1 deletes, default report-only, AGE_DAYS overrides
	python3 scripts/stale_branch_cleanup.py --repo $(GH_REPO) --age-days $(if $(AGE_DAYS),$(AGE_DAYS),3) $(if $(filter 1,$(APPLY)),--apply,)
sweep-concurrency-report: ## Report every scheduled workflow whose runs stack instead of superseding, with the measurement and the decision each one needs (issue #917)
	python3 scripts/sweep_concurrency.py report





# ---- secret scan: no credential VALUE may reach the repo (issue #360) -------
# `check-secret-output` reads the SHAPES a script prints; this reads the VALUE a
# human or a bot committed, which a shape rule cannot see (a PAT, a JWT, an
# AWS-style key, a bearer inside a URL). gitleaks runs in ITS OWN pinned image:
# the test image has no docker inside, so the scanner cannot live in it.
# `--redact` keeps the finding out of the log, and `.gitleaks.toml` allowlists only
# documented PLACEHOLDERS — a real value is removed and rotated, never allowlisted.
GITLEAKS_IMAGE := ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
GITLEAKS_RUN := $(RUNTIME) run --rm -v "$$PWD":/repo -w /repo $(GITLEAKS_IMAGE)

# ---- full-ruleset workflow lint (issue #329) ---------------------------------
# `check-workflows` kept the gate on the class of defect that makes GitHub REJECT a
# whole file. This runs the OTHER class — shellcheck findings and section syntax
# inside accepted files — over `.github/workflows/`, chained from `check-workflows`
# so the debt cannot re-accumulate. Digest-pinned like GITLEAKS_IMAGE (issue #2235:
# no mutable tags on gate images). The ONE ignore is the queue-key regex below:
# `concurrency.queue: max` in engine-bump.yml is load-bearing (issue #2294 — the
# queue is what stopped cancelled producers), GitHub accepts the key, and actionlint
# has not catalogued it yet. A second ignore pattern is a gate weakening; it must
# come with a filed issue.
ACTIONLINT_IMAGE := rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
ACTIONLINT_IGNORE := unexpected key "queue" for "concurrency" section
ACTIONLINT_RUN := $(RUNTIME) run --rm -v "$$PWD":/repo:ro -w /repo $(ACTIONLINT_IMAGE)

# The working-tree scan reads the COMMITTABLE set, not the whole filesystem (issue #382): `gitleaks
# dir` honours no .gitignore, so pointing it at the checkout reported findings inside
# `tests/__pycache__/*.pyc` — gitignored bytecode carrying the suites' own sentinels — and printed the
# "rotate the key" remediation for files nobody can commit. `scripts/secret_scan.py` exports
# `git ls-files -c -o --exclude-standard` (what `git add` would take) and runs the same pinned image
# and config against that tree.


.PHONY: check-empty-files
.PHONY: check-architecture-census
.PHONY: check-file-hygiene
.PHONY: file-hygiene-report


# The fix-bot's sweep asks the SAME question with the opposite consequence (issue #629): a `CI` failure
# report can arrive after its PR already merged or closed, and then there is nothing to repair — so an
# empty answer is an answer (exit 0, `number=`), never a red run. The merge gate above must keep failing
# loudly, which is why this is a separate target over one resolver rather than a shared default.


.PHONY: check-merge-on-red alert-merged-red stacked-merge-detect

# A bot's review VERDICT is a comment marker, never an approval (issue #852): every bot pushes with the
# owner's token, so `gh pr review --approve` on its own PR is refused and `reviewDecision` can never leave
# REVIEW_REQUIRED. The marker names the head it reviewed, and `auto_merge.decide()` accepts it ONLY at the
# PR's current head — a stale verdict counts for nothing. One producer, one format: scripts/bot_verdict.py.

.PHONY: check-holds holds-report bind-proof

.PHONY: check-main-ruleset main-ruleset-report main-ruleset-apply

.PHONY: check-pr-closing pr-closing-report
.PHONY: check-pr-acceptance
.PHONY: check-pr-acceptance-body
.PHONY: check-pr-openspec-change
.PHONY: check-pr-acceptance-form
.PHONY: check-pr-base
.PHONY: worktree-base
.PHONY: check-proc-gate proc-gate-report
.PHONY: check-report-header report-header-report

PR_BASE ?= origin/main
MODE ?= full
PR_HEAD ?= HEAD
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
PORT ?= 11434
ARCH_ARGS = $(if $(ARCH),--variant $(ARCH),$(ENGINE_ARGS))
# issue #178: a PR-scoped producer run sets MOVING=0 (from the engine-build workflow's
# moving_tags=false dispatch); the push/pull seams then pass --no-moving, so a PR build
# publishes and measures the unique pinned tag only and the moving :<arch>/:latest tags
# are moved solely by the run on main.
MOVING_FLAG = $(if $(filter 0 false,$(MOVING)),--no-moving,)
build-engine-%: ## Build one engine x arch image from its generated Dockerfile (build-engine-<engine>-<arch>)
	$(MAKE) build-engine ENGINE=$(patsubst %-$(lastword $(subst -, ,$*)),%,$*) ARCH=$(lastword $(subst -, ,$*))
run-engine-%: ## Run one engine x arch image (run-engine-<engine>-<arch> MODEL=…)
	$(MAKE) run-engine ENGINE=$(patsubst %-$(lastword $(subst -, ,$*)),%,$*) ARCH=$(lastword $(subst -, ,$*))
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

OS_OPTS := --rm -u root -v "$(REPO)":/repo:rw -w /repo $(OS_IMG)
# Same pin as openspec/Dockerfile ARG OPENSPEC_VERSION. macOS has no Docker, so
# openspec-validate installs this CLI instead of `docker run` (issue #120).
OPENSPEC_VERSION := 1.10.0

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
# Non-root container stages (issue #2563): run as the uid:gid that owns the
# bind-mounted checkout — uid 1000 (== the image default) on this host, the
# runner's uid on CI — so cache/bytecode writes land as the checkout's owner.
# HOME comes from the image (ENV HOME=/tmp), not a root-only override.
TEST_OPTS := --rm -u "$(shell id -u):$(shell id -g)" -v "$(ROOT)":/repo:rw -w /repo -e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN $(WORKTREE_MOUNT)
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
# Engine-driven stages KEEP `-u root` on purpose (issue #2563): this container
# reaches the HOST docker daemon through /var/run/docker.sock, which is
# `srw-rw---- root:docker` on this host — the plain uid mapping of TEST_OPTS
# could not connect. The image's non-root default stands for the plain stages.
ENGINE_TEST_ARGS := $(RUNTIME) run --rm -u root --network host \
	-v /var/run/docker.sock:/var/run/docker.sock -v "$(ROOT)":"$(ROOT)":rw -w "$(ROOT)" \
	-e HOME="$(CI_HOME)" -e LLGENIE_REGISTRY -e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN -e RUNTIME=docker $(WORKTREE_MOUNT)
engine_test = $(ENGINE_TEST_ARGS) $(foreach v,$(1),-e $(v)) $(TEST_IMG)
ENGINE_TEST_RUN := $(call engine_test,)
# .ci-home is written by root inside the engine container: remove it as root too,
# or the mapped uid cannot delete a root-owned tree (issue #2563).
CI_HOME_CLEAN := $(RUNTIME) run --rm -u root -v "$(ROOT)":/r $(TEST_IMG) rm -rf /r/.ci-home
TEST_RUN := $(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)
endif


# CUDA-toolkit (nvcc) + python image for the #84/#89 variant builds. The same
# image does all ubuntu-latest CPU + CUDA builds: builds use nvcc, and the
# 0.5B "hi" health check uses the bundled python + gguf/numpy/hf. (Metal builds
# run on macos-14 host toolchains — see the ci.yml jobs.)
VARIANT_IMG := gguf-tools/ci-variant:latest
VARIANT_RUN := $(RUNTIME) run $(VARIANT_OPTS) $(VARIANT_IMG)


# Native (non-container) engine tests are hardware-scoped (issue #114): only Metal runs
# natively, so they have test cases only on an Apple-Silicon Mac. On any other host
# (every Linux CI job, cuda/rocm/vulkan/cpu) these targets have no case for that
# hardware and say so; the Linux engines are tested through their images instead.
# NATIVE_HOST= simulates a non-Metal host.
NATIVE_HOST ?= $(shell [ "$$(uname -s)-$$(uname -m)" = "Darwin-arm64" ] && echo metal)
NATIVE_GUARD = [ "$(NATIVE_HOST)" = "metal" ] || { echo "[$@] native engines are Metal-only: this host ($$(uname -s) $$(uname -m)) has none; its engines are tested in their images (make test-engine)"; exit 0; };


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


# ---- ci-<job>: ONE make target per CI pipeline job (issue #117) -------------
# pipeline.yml runs each as one job, on Linux AND on macOS (issue #120: the same
# file, no combined jobs). The commands are the same on both OSes. Every target
# that runs in a container needs the pulled llgenie/test (or llgenie/openspec) image:
# CI pulls the test image first with `make test-image-pull` (a pull_request run that moved the
# hash defers the publish and builds it locally, issue #2518); the openspec gate pulls-or-builds
# with `make openspec-image` (a fork PR cannot publish a NEW hash, issue #1673).


# The gate below branches on $(HOST_OS), so it lives AFTER `HOST_OS := $(shell uname -s)`:
# make evaluates ifeq while it parses the file, and a conditional placed before that line
# would see an empty HOST_OS and take the Linux branch on macOS too.


verdict-roster: ## Print every workflow that can post a check-run at a PR head, the set `ci-verdict` judges, the difference, and the roster findings — a SUBSET check (`judged <= posters`), never equality (issue #2116)
	python3 scripts/verdict_roster.py report


.PHONY: check-host-space

.PHONY: reclaim-tmp-worktrees


help:
	@python3 scripts/make_help.py

