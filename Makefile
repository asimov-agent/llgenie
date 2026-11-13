# llgenie install Makefile.

include mk/gates.mk  # gates domain (issue #2457)
include mk/engines.mk  # engine domain (issue #2456)
include mk/security.mk
include mk/ci.mk
include mk/bots.mk  # bots domain (issue #2460)
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
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report changes-resolve check-pr-hygiene check-pr-agents-line check-pr-commit-checkboxes check-pr-sync-line pr-hygiene-report check-report-hygiene report-hygiene-report check-module-names check-claim-reader check-issue-bodies issue-bodies-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report security-scan security-scan-all security-verdict security-issues security-issues-reconcile security-issues-plan check-security-issues security-bot security-bot-pick check-security-bot sbom check-security-scan check-gitleaks-pin engine-pins scanner-image test-scanner-image scanner-digests pin-scanner-image-digests scanner-ref semgrep-rules-refresh publish-scanner-images ci-scanner-images check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report check-issue-bodies issue-bodies-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report scanner-image test-scanner-image scanner-digests pin-scanner-image-digests scanner-ref semgrep-rules-refresh publish-scanner-images ci-scanner-images check-scanner-images \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-actions actions-report update-actions \
	run-failure-reactor rebase-bot-agent check-docs docs-report changes-index changes-index-report check-pr-hygiene pr-hygiene-report auto-merge auto-merge-resolve auto-merge-channel fix-bot-resolve auto-merge-explain auto-merge-recheck verify-closure check-pr-authors pr-authors-report check-workflows workflows-report issue-refiner-pick issue-refiner issue-refiner-apply issue-dedup-pick issue-dedup issue-dedup-apply check-dispatch-forms dispatch-forms-report check-renovate renovate-report \
	arm-auto-merge arm-auto-merge-report \
	security-bumps security-bumps-plan check-security-bumps \
	agent-shell-keys-check \
	agent-fetch search-smoke require-env web-coverage issue-evidence \
	engine-bump-rebase generate-engine-params check-engine-params check-engine-coverage engine-coverage-report check-engine-source engine-source-report check-engine-capabilities engine-capabilities-report check-engine-launchers engine-launchers-report check-engine-pins-published check-engine-pins-valid engine-pins-published-report engine-build-pr-trigger engine-build-pr-trigger-report check-model-links model-links-report build-engine run-engine stop-engine list-engine-images engine-build-matrix test-engine-host ci-lint ci-unit ci-agents-read \
	ci-openspec ci-cpu-health ci-top-tier ci-install ci-install-dry-args ci-free-disk ci-slow-rows ci-scope ci-verdict verdict-roster test-engine-stage hf-cli-install bot-sync-main bot-sync-branch ci-wait-engine-images \
	ci-install-dry ci-install-run ci-install-uninstall test-env test-top-tier test-top-tier-ci test-top-tier-cli-ci test-top-tier-serve test-top-tier-serve-ci \
	check-agent-model model-pin-report check-agent-skills agent-skills-report test-agent-skills-live hermes-skills-register \
	sync-agent-profile check-agent-profiles agent-profiles-report tester-fold-live provision-agent-profiles \
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
install: bash-check venv-install engine-launchers link test-built-engine smoke provision-agent-profiles
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

# ---- the model pin the bots call (issue #405) --------------------------------
# The bots run the Hermes CLI in the agent image against ONE pinned snapshot through the alias
# `nous-deepseek`. That pin lives in two build inputs (the Dockerfile's ARG default and the
# install script's MODEL_ID default), and both used to name `deepseek/deepseek-v4.1-flash` —
# the OLDER, different model behind `canonical_slug …-20260910` — while the owner's host alias
# ran the `-1017` snapshot. Nothing compared them, and the one test asserted a substring any
# newer id satisfies. `scripts/agent_model_pin.py` is now the referee: stdlib only, no network,
# no key, and it names the file and the value it read when they disagree.
.PHONY: bot-preflight
.PHONY: bot-stamp-body
.PHONY: check-import-roots
.PHONY: check-package-layers
.PHONY: check-agent-profiles-ratchet
hermes-skills-register: ## Register the checkout's .hermes/skills in Hermes's config so `hermes -s <name>` resolves for every bot leg (HOME_DIR= the Hermes home, DIR= the skill dir; CHECK=1 verifies without writing — issue #577)
	python3 scripts/hermes_skills_register.py --home "$(if $(HOME_DIR),$(HOME_DIR),$(HOME)/.hermes)" --dir "$(if $(DIR),$(DIR),$(CURDIR)/.hermes/skills)" $(if $(CHECK),--check,)


# ---- a host agent's behaviour lives in the repo too (issue #791) ---------------------
# The two host agents (llgenie-planner, llgenie-issse-implementer) keep the same two kinds of
# file as the bot legs — SOUL.md and skills/<name>/SKILL.md — but under
# ~/.hermes/profiles/<profile>/, outside version control. An instruction that changes a
# credential-holding agent's behaviour was therefore the one change here nobody could diff.
# agents/<profile>/ is that behaviour's home now: `make sync-agent-profile` copies the tree INTO
# the profile's Hermes home (write, then read back — the shape scripts/hermes_skills_register.py
# uses) and CHECK=1 compares instead, naming the first differing path. The gate is what keeps the
# tree honest (a listed profile with no SOUL.md, a skill whose frontmatter name disagrees with its
# directory, a secret-shaped value, a planner SOUL.md that dropped "never merge").
sync-agent-profile: ## Copy agents/<PROFILE>/ into that profile's Hermes home (PROFILE=<profile>; CHECK=1 compares instead of writing and names the first differing path; FORCE=1 bypasses the refusal for a live file edited after the commit — read the refusal before forcing, it exists for a reason — HERMES_PROFILE_HOME= overrides the destination — issue #791)
	@test -n "$(PROFILE)" || { echo "Usage: make sync-agent-profile PROFILE=<profile> [CHECK=1] [FORCE=1]"; exit 2; }
	python3 scripts/agent_profile_sync.py --profile "$(PROFILE)" $(if $(CHECK),--check,) $(if $(FORCE),--force,)

provision-agent-profiles: ## Materialise EVERY lane's agents/<profile>/ into its Hermes home recursively, idempotently, then gate the result back against the tree (issue #2165) — the profile-creation/rebuild entrypoint (DEST=; CHECK=1 compares instead of writing; ROOT=) — HOST-ONLY: a CI runner has no live profiles to provision, but the caller wires it into install so a rebuild cannot skip it
	@python3 scripts/provision_agent_profiles.py $(if $(DEST),--dest "$(DEST)",) $(if $(CHECK),--check,) $(if $(ROOT),--root "$(ROOT)",)

.PHONY: provision-agent-profiles

skill-parity: ## Report live↔tree skill parity for every llgenie profile (issue #1924, Layer A) — HOST-ONLY and READ-ONLY: it diffs agents/<profile>/skills/ against the live ~/.hermes/profiles/<profile>/skills/ and prints live-only / tree-only counts and names; it NEVER writes (a CI runner has no live profiles, so this is one finding that needs a caller where they exist). No sync, no fold (#791/#1062)
	@python3 scripts/skill_parity.py report

.PHONY: skill-parity check-skill-code-parity
tester-fold-live: ## Enumerate a described live host-agent lane's files against its tree copy; COPY=1 writes live→tree (PROFILE=<profile>; issue #1079) — host-only: a CI runner has no live profile to fold from
	@test -n "$(PROFILE)" || { echo "Usage: make tester-fold-live PROFILE=<profile> [COPY=1]"; exit 2; }
	python3 scripts/fold-live-profile.py --profile "$(PROFILE)" $(if $(COPY),--copy,)

profile-drift-alarm: ## The SCHEDULED caller for #928: run on a host with live profiles, file ONE issue on drift (exit 2 = could not compare, 3 = drift)
	@python3 scripts/profile_drift_alarm.py --file-issue

.PHONY: profile-drift-alarm


.PHONY: check-tick-prompt

check-cron-drift: ## Fail when a live planner cron prompt (auto-approve-merge db0a3e1a3d7c, auto-rebase-resolve 71c5192ebdba) diverges from its versioned copy under agents/llgenie-planner/prompts/ (issue #2359) — host-only: a CI runner has no live jobs.json; exit 0 all identical, 1 any drift, 2 a read/missing failure (LIVE=; ROOT=), HOST-ONLY
	@python3 scripts/check_cron_drift.py $(if $(LIVE),--live "$(LIVE)",) $(if $(ROOT),--root "$(ROOT)",)

.PHONY: check-cron-drift

verify-lane-contract: ## Verify each live llgenie lane's SOUL commits to the behavioural contract (report line, never-merge, bookend, versioned-edit, own duty, communication + materialised skills) — host-only: a CI runner has no live ~/.hermes profiles; prints `N/13 lanes pass` and names FAIL lanes + the missing element (issue #2260)
	@python3 scripts/verify_lane_contract.py

.PHONY: verify-lane-contract

profile-drift: ## Fail when a tree copy is a PREFIX of the live rulebook (issue #928) — host-only: a CI runner has no live profiles, so this is the one finding that needs a caller where they exist
	@python3 scripts/check_agent_profiles.py check --only live-longer

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


lane-preflight: ## Run the FAST gates before a host lane pushes, printing one line per gate and a final verdict; imports FAST_GATES from issue_bot_gates.py (one list) and refuses a dirty tree so the verdict describes the would-be-pushed head (issue #1058)
	python3 scripts/lane_preflight.py run

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


agent-repo-ownership: ## Give the mounted checkout back to the invoking user after a containerized agent leg (a root-run leg leaves `.git/objects` unwritable, so the next `git add` dies with "insufficient permission"; issue #770)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm -v "$(OWNERSHIP_DIR):/repo" --entrypoint chown \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) -R $(shell id -u):$(shell id -g) /repo)


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

_hermes-smoke: # (internal) one real Hermes call that MUST use its terminal tool. Invoked inside
# the agent image by the public `hermes-smoke` target.
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/hermes_smoke.py run --alias $(nous-model) --reasoning low
nerve-profile-check: ## Probe the rule the agent image build enforces: a nerve setting whose module the selected profile does not register is inert, so the build fails (issue #611)
	python3 scripts/nerve_profile_check.py --self-test

memory-install:
	@[ "$${DRY_RUN:-0}" = "1" ] && python3 scripts/memory_bootstrap.py install --dry-run || python3 scripts/memory_bootstrap.py install

memory-bootstrap:
	python3 scripts/memory_bootstrap.py bootstrap $${PROFILE:+--profiles $$PROFILE} $${DRY_RUN:+--dry-run}

memory-verify:
	python3 scripts/memory_bootstrap.py verify $${PROFILE:+--profiles $$PROFILE}

memory-check:
	python3 scripts/memory_bootstrap.py verify $${PROFILE:+--profiles $$PROFILE}

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





agent-image-ref: ## Print the GHCR :latest ref every agent pull uses (publish points it at the content hash)
	@python3 scripts/ci_images.py latest agent



# ---- secret scan: no credential VALUE may reach the repo (issue #360) -------
# `check-secret-output` reads the SHAPES a script prints; this reads the VALUE a
# human or a bot committed, which a shape rule cannot see (a PAT, a JWT, an
# AWS-style key, a bearer inside a URL). gitleaks runs in ITS OWN pinned image:
# the test image has no docker inside, so the scanner cannot live in it.
# `--redact` keeps the finding out of the log, and `.gitleaks.toml` allowlists only
# documented PLACEHOLDERS — a real value is removed and rotated, never allowlisted.
GITLEAKS_IMAGE := ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
GITLEAKS_RUN := $(RUNTIME) run --rm -v "$$PWD":/repo -w /repo $(GITLEAKS_IMAGE)

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


bind-proof: ## Bind a proof run's head_sha to the PR head it is cited for — fail unless the run proved the CURRENT head (PR= RUN=, issue #1293)
	@test -n "$(PR)" && test -n "$(RUN)" || { echo "Usage: make bind-proof PR=<n> RUN=<run-id>"; exit 1; }
	python3 scripts/bind_proof.py --pr $(PR) --run $(RUN)

.PHONY: check-holds holds-report bind-proof

check-main-ruleset: ## CI: fail when the main ruleset has no required_status_checks or misses a pinned context (the missing merge-block gate, issue #1400) — runs in the monitor workflow main-ruleset.yml; exits 2 when the ruleset cannot be read
	python3 scripts/check_main_ruleset.py check --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),)

main-ruleset-report: ## Print the main ruleset's measured state and the pinned required contexts, always exit 0 (issue #1400)
	python3 scripts/check_main_ruleset.py report --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),)

main-ruleset-apply: ## DRY by default: print the add-only required_status_checks PUT body; APPLY=1 with an admin token performs it (owner-admin-only, issue #1400)
	python3 scripts/check_main_ruleset.py apply --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),) $(if $(filter 1,$(APPLY)),--apply,)

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

test-image-pull: ## CI: pull the published test image (hash of its Dockerfile + lockfiles) as $(TEST_IMG); a push run fails if not published and never builds; a pull_request run defers the publish to the landing run and builds it locally (issue #2518)
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

test-board-ownership-host: ## HOST-ONLY proof of #2353 AC3 (runs the real hermes CLI against a throwaway HERMES_KANBAN_DB; recorded host-only in unit-suite.json + host-only-wiring.json)
	@$(PY) -m pytest tests/test_kanban_single_card_reassign.py -p no:cacheprovider -q

test-recall-step: ## Host proof of the orchestrator STEP 2 recall fallback (issue #2186): asserts the pinned 9177 recall returns `results` and that the wrong default port 8888 fails while 9177/health succeeds. Needs the live hindsight daemon on 127.0.0.1:9177 (HINDSIGHT_API_PORT in ~/.hindsight/profiles/hermes.env), which no CI runner has, so it is kept OUT of the hermetic gate (tests/fixtures/unit-suite.json) and run on the tick host
	@$(PY) -m pytest tests/test_procedure_recall_step.py -p no:cacheprovider -q

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

hf-cli-install: ## Provision the `hf` downloader the engine-build tiny-test-model step uses (issue #2380): install the EXACT huggingface_hub version pinned in tools/requirements.in — never a floating `>=`, which drifted to a 2.x whose `cli` extra was removed (AGENTS.md: every CI command is a make target).
	@spec="$$(grep '^huggingface_hub==[0-9]' tools/requirements.in || true)"; \
	test -n "$$spec" || { echo "[hf-cli-install] tools/requirements.in pins no huggingface_hub==<version>"; exit 1; }; \
	echo "[hf-cli-install] uv tool install $$spec (from tools/requirements.in)"; \
	uv tool install "$$spec"

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

