# llgenie — the top Makefile, split into six domain files (issue #800).
#
# This file keeps the shared environment (SHELL/HOME/BIN/PATH/REPO/...), the `.PHONY`
# declaration, the `help`/`version` targets and the `include`s. Every stage/gate target
# lives in mk/*.mk, byte-for-byte unchanged: a change to one domain touches one small file.

.DEFAULT_GOAL := bash-check

# ---- shared environment (every mk/*.mk recipe references these) ----------------

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
	test test-unit test-agents-read agents-read-venv test-install test-install-ci test-install-host test-install-trend test-health test-health-host test-recall-step download-test-model \
	test-image test-image-pull openspec-image-pull publish-ci-images publish-agent-image agent-image-push-check agent-image agent-image-pull ci-image-refs test-clean lint lint-fix loop loop-harness chained sweep-concurrency-report \
	build-server build-variant serve-variant test-serve-variant stop-serve-variant install-prism-cpu install-upstream-cpu \
	install-prism-cuda install-upstream-cuda install-prism-metal install-upstream-metal \
	sync-registry check-registry skills-validate engine-list engine-hardware engine-plan engine-check engine-install engine-detect engine-smoke test-engine test-engine-serve ci-engine-images build-engine-base build-engines generate-build-engine-params test-engine-image push-engine test-published-engine test-install-published engine-launchers test-built-engine test-uninstalled engine-capability-serve \
		sync-quant-catalog check-quant-catalog render-trend-list-matrix check-trend-list-matrix render-engine-skill-gap check-engine-skill-gap \
	render-vram-scope-view check-vram-scope-view \
	engine-gate-report engine-skill-gap engine-skill-gap-md spawn-engine-skill-issues engine-skill-scaffold registry-change-report sync-change-issue registry-review-brief registry-sync-review registry-review-publish sync-strata-models check-strata-models check-wiring wiring-report check-secret-output secret-output-report \
	secret-scan secret-scan-history secret-scan-self-test \
	queued-alarm check-zero-job-pending stale-branch-cleanup issue-cleaner-scan issue-cleaner-apply worktree-report worktree-prune fix-loop fix-loop-image fix-bot-sweep fix-bot-report agent-image-ref issue-bot-dispatch issue-bot-open-pr issue-bot-image ci-requeue-cancelled ci-frozen-reaper issue-bot-pr-body-check agent-repo-ownership \
	issue-bot-triage issue-bot-changed issue-bot-verdict issue-bot-gates issue-bot-gates-check lane-preflight implement-issue hermes-smoke agent-jev-preflight jev-preflight-required nerve-profile-check code-review-scan code-review-file rebase-bot-sweep rebase-bot rebase-bot-abort \
	memory-install memory-bootstrap memory-verify memory-check \
	engine-params-review-brief engine-params-review engine-params-review-apply \
	architecture-bot-brief architecture-bot-doc architecture-bot-publish architecture-bot check-arms arms-report \
	scrub-log \
	check-pr-heads pr-heads-report bot-verdict bot-verdict-read \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report changes-resolve check-pr-hygiene check-pr-agents-line check-pr-sync-line pr-hygiene-report check-report-hygiene report-hygiene-report check-module-names check-claim-reader check-issue-bodies issue-bodies-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report security-scan security-scan-all security-verdict security-issues security-issues-reconcile security-issues-plan check-security-issues security-bot security-bot-pick check-security-bot sbom check-security-scan check-gitleaks-pin engine-pins scanner-image test-scanner-image scanner-digests scanner-ref publish-scanner-images ci-scanner-images check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report check-issue-bodies issue-bodies-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report scanner-image test-scanner-image scanner-digests scanner-ref publish-scanner-images ci-scanner-images check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-actions actions-report update-actions \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-renovate renovate-report \
	arm-auto-merge arm-auto-merge-report \
	security-bumps security-bumps-plan check-security-bumps \
	agent-shell-keys-check \
	agent-fetch search-smoke require-env web-coverage issue-evidence \
	engine-bump-rebase generate-engine-params check-engine-params check-engine-coverage engine-coverage-report check-engine-source engine-source-report check-engine-capabilities engine-capabilities-report check-engine-launchers engine-launchers-report check-engine-pins-published check-engine-pins-valid engine-pins-published-report engine-build-pr-trigger engine-build-pr-trigger-report check-model-links model-links-report build-engine run-engine stop-engine list-engine-images engine-build-matrix test-engine-host ci-lint ci-unit ci-agents-read \
	ci-openspec ci-cpu-health ci-top-tier ci-install ci-install-dry-args ci-free-disk ci-slow-rows ci-scope ci-verdict verdict-roster test-engine-stage bot-sync-main bot-sync-branch ci-wait-engine-images \
	ci-install-dry ci-install-run ci-install-uninstall test-env test-top-tier test-top-tier-ci test-top-tier-cli-ci test-top-tier-serve test-top-tier-serve-ci \
	check-agent-model model-pin-report check-agent-skills agent-skills-report test-agent-skills-live hermes-skills-register \
	sync-agent-profile check-agent-profiles agent-profiles-report tester-fold-live provision-agent-profiles \
	test-hub-live test-strata-live test-engine-bump-live test-native-engines test-native-engine-light test-variant-image \
	bash-check engine-bump engine-bump-daily engine-bump-plan engine-derive generate-requirements openspec-tasks-check check-registry-keys ci-engines all-pipelines-sweep bots-restore-health targets-coverage \
	check-host-space reclaim-tmp-worktrees

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
export LLGENIE_REGISTRY ?= ghcr.io/asimov-agent
REGISTRY ?= tests/fixtures/trending-models.json
ENGINE_ARGS = $(if $(BACKEND),--backend $(BACKEND),)
REGISTRY_REVIEW_BRIEF ?= registry-review-in.md
REGISTRY_REVIEW_OUT ?= registry-review.md
.PHONY: bot-preflight
.PHONY: bot-stamp-body
.PHONY: check-import-roots
.PHONY: check-package-layers
.PHONY: check-agent-profiles-ratchet
.PHONY: provision-agent-profiles
.PHONY: skill-parity check-skill-code-parity
.PHONY: profile-drift-alarm
.PHONY: check-tick-prompt
.PHONY: check-cron-drift
.PHONY: verify-lane-contract
.PHONY: profile-drift
REBASE_BOT_SKILLS := rebase-conflict,bot-unattended
.PHONY: orchestrator-tick orchestrator-tick-pending orchestrator-tick-report
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
AGENT_IMAGE := llgenie/agent:latest
#: The checkout `make agent-repo-ownership` gives back to the invoking user (issue #770).
OWNERSHIP_DIR ?= $(CURDIR)
AGENT_SHELL_CHECK_KEYS ?= $(AGENT_SHELL_KEYS)
DOC ?= docs/ARCHITECTURE.md
ARCH_BRIEF ?= architecture-brief.md
STAMP ?= $(shell date -u +%Y%m%dT%H%M)
GITLEAKS_IMAGE := ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
GITLEAKS_RUN := $(RUNTIME) run --rm -v "$$PWD":/repo -w /repo $(GITLEAKS_IMAGE)
.PHONY: check-empty-files
.PHONY: check-architecture-census
.PHONY: check-merge-on-red alert-merged-red stacked-merge-detect
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
UNSUPPORTED ?=
PORT ?= 11434
ARCH_ARGS = $(if $(ARCH),--variant $(ARCH),$(ENGINE_ARGS))
version: ## Show numpy/gguf versions inside the venv
	$(MAKE) -C tools version
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
VARIANT_IMG := gguf-tools/ci-variant:latest
VARIANT_RUN := $(RUNTIME) run $(VARIANT_OPTS) $(VARIANT_IMG)
PY312             ?= python3.12
AGENTS_READ_VENV  ?= $(HOME)/.cache/llgenie/agents-read-venv
HERMES_AGENT_PIN  := hermes-agent==0.19.0

AGENTS_READ_STAMP := $(AGENTS_READ_VENV)/.installed-$(HERMES_AGENT_PIN)
NATIVE_HOST ?= $(shell [ "$$(uname -s)-$$(uname -m)" = "Darwin-arm64" ] && echo metal)
NATIVE_GUARD = [ "$(NATIVE_HOST)" = "metal" ] || { echo "[$@] native engines are Metal-only: this host ($$(uname -s) $$(uname -m)) has none; its engines are tested in their images (make test-engine)"; exit 0; };
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
	@echo "  make lane-preflight             run the FAST gates before a host lane pushes: one line per gate, a final OK|FAILED verdict, refuses a dirty tree so the verdict describes the would-be-pushed head (issue #1058)"
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

# ---- the domain files (issue #800): one small file per stage ----
include mk/engines.mk  # 88 targets
include mk/gates.mk  # 62 targets
include mk/ci.mk  # 65 targets
include mk/security.mk  # 35 targets
include mk/bots.mk  # 90 targets
include mk/install.mk  # 26 targets
