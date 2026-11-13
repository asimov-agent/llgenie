# llgenie install Makefile.

include mk/gates.mk  # gates domain (issue #2457)
include mk/engines.mk  # engine domain (issue #2456)
include mk/security.mk
include mk/install.mk  # install domain (issue #2461)
include mk/ci.mk
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
rebase-bot-sweep: ## Which ONE open PR needs rebasing (BEHIND/DIRTY against main): prints action/pr/head_* and the reason for every pass-over
	python3 scripts/rebase_bot_sweep.py --repo $(GH_REPO) $(if $(OWN_FORK),--own-fork $(OWN_FORK),) $(if $(SKIP),--skip "$(SKIP)",)

# ---- the model pin the bots call (issue #405) --------------------------------
# The bots run the Hermes CLI in the agent image against ONE pinned snapshot through the alias
# `nous-deepseek`. That pin lives in two build inputs (the Dockerfile's ARG default and the
# install script's MODEL_ID default), and both used to name `deepseek/deepseek-v4.1-flash` —
# the OLDER, different model behind `canonical_slug …-20260910` — while the owner's host alias
# ran the `-1017` snapshot. Nothing compared them, and the one test asserted a substring any
# newer id satisfies. `scripts/agent_model_pin.py` is now the referee: stdlib only, no network,
# no key, and it names the file and the value it read when they disagree.
.PHONY: bot-preflight
bot-preflight: ## Fetch origin/main, fast-forward a behind checkout, and record the AGENTS.md this run is measured against (issue #792); when the working diff touches agents/<profile>/, surfaces the #1724 SYNC-line obligation (BODY=<prospective PR body> refuses a missing/mis-cited SYNC line, issue #1782)
	python3 scripts/bot_preflight.py $(if $(CHECK),--check,) $(if $(BODY),--body-file "$(BODY)",)
.PHONY: bot-stamp-body
bot-stamp-body: ## Stamp BODY=<pr body file> in place (or into OUT=) with the `AGENTS:`/`BASE:` pair measured at origin/main — the ONE stamp authority every bot PR producer calls before `gh pr create`/`gh pr edit`, so a bot PR never opens unstamped (issue #2050); BASE=/REFS= name the main ref a producer's checkout actually stands on
	@test -n "$(BODY)" || { echo "Usage: make bot-stamp-body BODY=<pr body file> [OUT=<file>] [BASE=origin/main] [REFS=origin/HEAD,main]"; exit 1; }
	python3 scripts/bot_preflight.py --stamp "$(BODY)" $(if $(OUT),--out "$(OUT)",) $(if $(BASE),--base "$(BASE)",) $(if $(REFS),--refs "$(REFS)",)
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

check-tick-prompt: ## Fail when the live orchestrator cron prompt diverges from the versioned copy under agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md (issue #2159) — host-only: a CI runner has no live jobs.json; exit 0 identical, 1 diverged, 2 a read/missing failure (LIVE=; VERSIONED=), HOST-ONLY
	@python3 scripts/check_tick_prompt.py $(if $(LIVE),--live "$(LIVE)",) $(if $(VERSIONED),--versioned "$(VERSIONED)",)

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
rebase-bot-agent: ## Ask Hermes to resolve a stopped rebase (the conflict prompt arrives on STDIN); runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm -i --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'hermes -z "$$(cat) Follow the preloaded skill rebase-conflict; the prompt above carries the conflicted files." -s $(REBASE_BOT_SKILLS) $(nous-alias) --reasoning medium --yolo')
# Hermes runs directly there, NOT through `make _rebase-bot-agent`: the container's /repo/Makefile
# is the conflicted file the agent was asked to resolve, and make cannot parse it (issue #460).

rebase-bot-abort: ## Abort a stopped rebase and return the tree to main, so the next decision in the same run starts clean (issue #462)
	@git rebase --abort >/dev/null 2>&1 || true
	@git checkout -q main >/dev/null 2>&1 || true
	@echo "[rebase-bot] abort: tree back on main"

rebase-bot: ## Rebase ONE PR onto main (agent-resolved conflicts), verify the structure, then push --force-with-lease to the PR's head remote. Never merges. Needs PR=/HEAD_BRANCH= [HEAD_REPO=] [DRY=1]
	@test -n "$(PR)" && test -n "$(HEAD_BRANCH)" || { echo "Usage: make rebase-bot PR=<n> HEAD_BRANCH=<branch> [HEAD_REPO=<owner>] [REPO=] [DRY=1]"; exit 1; }
	PR=$(PR) HEAD_BRANCH="$(HEAD_BRANCH)" HEAD_REPO=$(if $(HEAD_REPO),$(HEAD_REPO),asimov-agent) \
	  REPO=$(GH_REPO) $(if $(DRY),DRY=1,) scripts/rebase_bot.sh
# ---- issue-refiner: reviews NOT-yet-implemented issues on the implementer's spare capacity
# (issue #263). One issue per run, ONE comment + the `agent:refined` label, and never a PR.
issue-refiner-pick: ## Spare capacity (the implementer's cap is spent)? -> the oldest issue that is not decided, claimed or already PR'd -> refine-in.md (DRY=1 previews; REPO= picks the repo)
	python3 scripts/issue_refiner.py pick --repo $(GH_REPO) $(if $(DRY),--dry,)
issue-refiner: ## Hermes REVIEWS the picked issue (reads refine-in.md: the thread + the review instruction) and writes its verdict to refine.md. No branch, no PR, nothing else touched; runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	@$(MAKE) --no-print-directory agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY
	@$(MAKE) --no-print-directory issue-evidence ISSUE_FILE=refine-in.md OUTDIR=fetched MAX=$(if $(MAX),$(MAX),3)
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _issue-refiner')
_issue-refiner: # (internal) the host recipe the agent image runs: the review, not the code
	hermes -z "Follow the preloaded skill issue-refiner. Its Input is refine-in.md (with fetched/index.md as the pre-fetched evidence) and its Output is refine.md, in the shape the skill prints." -s issue-refiner,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
issue-refiner-apply: ## Apply the review in refine.md: ONE comment on the issue + the agent:refined label (never a PR; refuses a `refined` verdict with no RESTATED block)
	@test -n "$(ISSUE)" || { echo "Usage: make issue-refiner-apply ISSUE=<n> [REPO=<owner/repo>]"; exit 1; }
	python3 scripts/issue_refiner.py apply refine.md --repo $(GH_REPO) --issue $(ISSUE)

issue-dedup-pick: ## Which two unclaimed open issues look like the same defect? -> dedup-in.md, older as canonical (DRY=1 previews; REPO= picks the repo; issue #553)
	python3 scripts/issue_dedup.py pick --repo $(GH_REPO) $(if $(DRY),--dry,)
issue-dedup: ## Hermes decides whether the picked pair is the SAME defect (reads dedup-in.md) and writes dedup.md; no comment, no close, nothing else touched; runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #553)
	@python3 scripts/require_env.py NOUS_API_KEY
	@$(MAKE) --no-print-directory agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=NOUS_API_KEY
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _issue-dedup')
_issue-dedup: # (internal) the host recipe the agent image runs: the decision, not the change
	hermes -z "Follow the preloaded skill issue-dedup. Its Input is dedup-in.md and its Output is dedup.md, in the shape the skill prints." -s issue-dedup,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
issue-dedup-apply: ## Apply dedup.md: retire the COPY with a comment citing the canonical + agent:duplicate, close it, and queue the canonical (COPY=<n>; never touches a claimed issue; refuses a duplicate without EVIDENCE)
	@test -n "$(COPY)" || { echo "Usage: make issue-dedup-apply COPY=<n> [FILE=dedup.md] [REPO=<owner/repo>] [DRY=1]"; exit 1; }
	python3 scripts/issue_dedup.py apply $(if $(FILE),$(FILE),dedup.md) --copy $(COPY) --repo $(GH_REPO) $(if $(DRY),--dry,)

# The documentation review of an engine's DERIVED build parameters (issue #583). The bump proves the
# params COMPILE; this leg checks them against the engine's own docs for the arch being built. The host
# stays the writer: the agent may only propose a `-D` flag whose evidence it quotes from the upstream
# tree at the pin, and the apply step drops anything it cannot find there.
issue-bot-dispatch: ## The issue-implementer's dispatcher: cap (3/day) -> pick one labeled/ready issue -> claim -> write issue.md + branch (REPO= issue-bot.yml sets it; FORCE_ISSUE= pins a manual run; DRY=1 previews)
	python3 scripts/issue_implementer.py dispatch --repo "$(GH_REPO)" $(if $(FORCE_ISSUE),--force-issue $(FORCE_ISSUE),) $(if $(DRY),--dry,) $(if $(TODAY),--today $(TODAY),)
# The orchestrator tick's dispatch producer (issue #1125). It measures the two facts the tick
# dispatches (a DIRTY/CONFLICTING PR, an agent:implement issue with no live claim), appends the delta
# to an append-only OUTBOX and fsyncs it BEFORE the state advances, then prints the pending lines and
# acknowledges them. `NO_ACK=1` prints and acknowledges nothing — the exact shape of a delivery that
# was lost — and the next run re-emits the same bytes from the outbox.
# The recipes are prefixed with `@` on purpose: STDOUT IS THE DELIVERY. make echoes a recipe line to
# stdout otherwise, so the receiver would get the command as its first "dispatch line" (measured: 54
# stdout lines for 53 outbox records). The numbers go to stderr; stderr is not the payload.
orchestrator-tick: ## The orchestrator tick's dispatch producer (issue #1125): measure -> append to the outbox BEFORE advancing state -> emit the pending lines, each stamped [measured HH:MM:SSZ]; a merged PR / closed issue is never emitted (REPO=; STATE=; OUTBOX=; NO_ACK=1 simulates a lost delivery; NOW= pins the clock)
	@python3 scripts/orchestrator_tick.py emit --repo "$(GH_REPO)" $(if $(STATE),--state "$(STATE)",) $(if $(OUTBOX),--outbox "$(OUTBOX)",) $(if $(NO_ACK),--no-ack,) $(if $(NOW),--now "$(NOW)",)
orchestrator-tick-pending: ## Print the lines the tick's outbox still holds undelivered — what a lost delivery would have said, with each fact's [measured HH:MM:SSZ] — and acknowledge nothing (issue #1125; REPO=; STATE=; OUTBOX=)
	@python3 scripts/orchestrator_tick.py pending --repo "$(GH_REPO)" $(if $(STATE),--state "$(STATE)",) $(if $(OUTBOX),--outbox "$(OUTBOX)",)
orchestrator-tick-report: ## The tick producer's outbox numbers: facts, records, acknowledged, suppressed, pending, suppressible — no dispatch line on stdout (issue #1125; REPO=; STATE=; OUTBOX=)
	@python3 scripts/orchestrator_tick.py report --repo "$(GH_REPO)" $(if $(STATE),--state "$(STATE)",) $(if $(OUTBOX),--outbox "$(OUTBOX)",)
.PHONY: orchestrator-tick orchestrator-tick-pending orchestrator-tick-report
issue-bot-open-pr: ## Open the draft-free PR linking ISSUE from BRANCH, its body built from the agent's pr-body.md + the commit's stat and titled from the issue (never merges; refuses a body with missing Issue:/Fix:/Benefit:/Technical: parts; REPO=/ISSUE=/BRANCH= from the workflow)
	@test -n "$(ISSUE)" && test -n "$(BRANCH)" || { echo "Usage: make issue-bot-open-pr REPO=<owner/repo> ISSUE=<n> BRANCH=<agent/issue-n-slug>"; exit 1; }
	python3 scripts/issue_implementer.py open-pr --repo "$(GH_REPO)" --issue $(ISSUE) --branch "$(BRANCH)" --body-file $(if $(BODY_FILE),$(BODY_FILE),pr-body.md)
# The agent step: Hermes reads issue.md + AGENTS.md at the repo root and
# implements it. AGENTS.md is the authority (Makefile-driven verification, no
# skipped tests, business logic never mocked, one make path per stage, wiring).
# Runs on the CI runner with NOUS_API_KEY from a secret; #238 wires the
# token/plugin into the agent image. The model alias matches the sibling repo.
# Hermes's bundled `nous` provider is OAuth-only, so `--provider nous` cannot work with a
# secret. The image's install script writes a custom-provider alias instead (provider=custom,
# base_url=the Nous OpenAI-compatible endpoint, key_env=NOUS_API_KEY) and this is the model
# name every call uses. `-m` is the MODEL flag (a bare `-m "text"` sets the model to text).
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

issue-bot-image: ## Build/pull the agent image the issue-bot runs in (the same image the fix-bot uses; alias of agent-image)
	python3 scripts/ci_images.py ensure agent

issue-bot-triage: ## Hermes REVIEWS the issue (issue.md: body + the whole comment thread + the decision block) and writes its verdict to triage.md (implement | refine | close). No PR, nothing else touched; runs INSIDE the agent image; the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING -e REPO \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _issue-bot-triage')

_issue-bot-triage: # (internal) the host recipe the agent image runs: the decision, not the code
	hermes -z "Follow the preloaded skill issue-triage. Its Input is issue.md and its Output is triage.md, in the shape the skill prints." -s issue-triage,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

issue-bot-changed: ## Did the implement step actually change the tree? Prints changed=true|false, the bot's own run inputs excluded; exit 2 when git cannot read the tree (issue #428)
	python3 scripts/issue_implementer.py changed
issue-bot-verdict: ## Apply the agent's TRIAGE verdict from triage.md: implement -> nothing (the PR path runs), refine -> ONE comment + agent:refined (no PR), close -> comment with the cited evidence + agent:closed (refused without EVIDENCE)
	@test -n "$(ISSUE)" || { echo "Usage: make issue-bot-verdict ISSUE=<n> [REPO=<owner/repo>]"; exit 1; }
	python3 scripts/issue_implementer.py apply-verdict triage.md --repo $(GH_REPO) --issue $(ISSUE)

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
issue-bot-gates: ## Run the FAST repository gates in order, stopping at the FIRST failure and naming it (lint, workflows, wiring, docs, PR hygiene, OpenSpec tasks): what the issue-bot runs after the implement step and BEFORE it pushes, so a bookkeeping red never reaches the PR (issue #475)
	python3 scripts/issue_bot_gates.py run

issue-bot-gates-check: ## CI: fail when a ci-unit gate is classified neither fast nor deferred, a fast gate is unwired or not .PHONY, or the issue-bot's gate step is not between the change detection and the push (issue #475)
	python3 scripts/issue_bot_gates.py check

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
bot-sync-main: ## Fetch upstream main and reset the working tree to it, so a NEW branch starts from latest main (issue #303); fails loudly when main cannot be reached
	@bash scripts/bot_sync_main.sh reset

bot-sync-branch: ## Fetch upstream main and rebase the checked-out PR branch onto it before repairing (issue #303); exit 2 means the rebase conflicts and is left to the rebase-bot
	@bash scripts/bot_sync_main.sh rebase

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
web-coverage: ## Which URLs a bot run depends on, and do they resolve (a fixture list, or ISSUE_FILE=); non-zero on a dead one — no model call, no key
	python3 scripts/web_evidence.py check $(if $(ISSUE_FILE),$(ISSUE_FILE),tests/fixtures/bot-facing-urls.md) $(if $(URLS),--urls $(URLS),)

issue-evidence: ## Pre-fetch the URLs an issue names so the agent reviews against real text: drives the ONE `agent-fetch` leg, capped, never fatal (ISSUE_FILE=, OUTDIR=fetched, MAX=3)
	@test -n "$(ISSUE_FILE)" || { echo "Usage: make issue-evidence ISSUE_FILE=<path> [OUTDIR=fetched] [MAX=3]"; exit 1; }
	@python3 scripts/web_evidence.py fetch $(ISSUE_FILE) --outdir $(if $(OUTDIR),$(OUTDIR),fetched) --max $(if $(MAX),$(MAX),3)

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
code-review-scan: ## The code-review bot's checks: tree + pipelines -> findings (REPO=; STATIC=1 skips the checks that read the GitHub API; JSON=1 for machine output; no model spend, writes nothing)
	python3 scripts/code_review.py scan --repo "$(GH_REPO)" $(if $(STATIC),--static-only,) $(if $(JSON),--json,)
code-review-file: ## File ONE issue per NEW code-review finding, capped per run (REPO=; CAP= issues per run, default 3; DRY=1 previews) — never edits code, never merges
	@test -n "$(REPO)" || { echo "Usage: make code-review-file REPO=<owner/repo> [CAP=3] [DRY=1]"; exit 1; }
	python3 scripts/code_review.py file --repo "$(GH_REPO)" $(if $(CAP),--cap $(CAP),) $(if $(DRY),--dry,)

# ---- the architecture bot (issue #449) ---------------------------------------
# `docs/ARCHITECTURE.md` is the map of the shipped path, and it ages the moment the tree moves.
# This bot re-derives it every 6 hours: a deterministic brief from real `git` state (no model),
# ONE Hermes leg that may write only that doc, and a deterministic publish that files ONE issue
# and ONE linked PR. A run with no drift files nothing, and no run ever merges.
DOC ?= docs/ARCHITECTURE.md
ARCH_BRIEF ?= architecture-brief.md
STAMP ?= $(shell date -u +%Y%m%dT%H%M)

architecture-bot-brief: ## Derive the architecture doc's brief from the real tree and the drift since the doc's last commit (DOC= path, OUT= path; no model, writes only the brief — issue #449)
	python3 scripts/architecture_bot.py brief --doc "$(DOC)" --out "$(ARCH_BRIEF)"

architecture-bot-doc: ## Rewrite the architecture doc with Hermes INSIDE the agent image from the brief (DOC=; the doc is the ONLY writable file); the transcript is REDACTED (issue #449)
	@python3 scripts/require_env.py NOUS_API_KEY
	@test -f "$(ARCH_BRIEF)" || { echo "Run 'make architecture-bot-brief' first: $(ARCH_BRIEF) is missing"; exit 1; }
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e HERMES_REASONING \
	  -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _architecture-bot-doc DOC="$(DOC)" ARCH_BRIEF="$(ARCH_BRIEF)"')

_architecture-bot-doc: # (internal) the host recipe the agent image runs: only the doc is writable
	$(MAKE) _agent-jev-preflight
	hermes -z "Follow the preloaded skill architecture-doc. The brief is $(ARCH_BRIEF); the only file you may write is $(DOC)." -s architecture-doc,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

architecture-bot-publish: ## File ONE issue + ONE linked PR for the doc change (REPO=; DOC=; STAMP=; DRY=1 previews) — nothing without drift, never merges (issue #449)
	@test -n "$(REPO)" || { echo "Usage: make architecture-bot-publish REPO=<owner/repo> [DOC=docs/ARCHITECTURE.md] [DRY=1]"; exit 1; }
	python3 scripts/architecture_bot.py publish --repo "$(GH_REPO)" --doc "$(DOC)" --stamp "$(STAMP)" $(if $(DRY),--dry,)

architecture-bot: ## Run the architecture bot locally end to end: brief -> doc -> issue + PR (needs NOUS_API_KEY and REPO=; DRY=1 stops at the preview)
	@$(MAKE) architecture-bot-brief DOC="$(DOC)"
	@$(MAKE) architecture-bot-doc DOC="$(DOC)"
	@$(MAKE) architecture-bot-publish REPO="$(REPO)" DOC="$(DOC)" $(if $(DRY),DRY=1,)

# ---- the acceptance-tick audit (issue #2631, follow-up #2288) -----------------
# #2288 made NEW acceptance ticks honest; this tool re-measures the WHOLE closed-issue
# corpus and resolves the recorded-stale ticks append-only: supersession notes, never
# rewrites. `audit` exits 0 only when zero unsuperseded stale ticks remain.
AUDIT_OUT ?= audit-out

audit-ticks: ## Re-measure the acceptance-tick corpus over all closed issues; exit 0 only when zero unsuperseded stale ticks remain (issue #2631)
	python3 scripts/audit_acceptance_ticks.py audit --repo "$(GH_REPO)" --roster "$(AUDIT_OUT)/roster.json"

audit-ticks-notes: ## Render the supersession note bodies for the roster's remaining stale ticks (AUDIT_OUT=; append-only, ticks stay as written) — issue #2631
	python3 scripts/audit_acceptance_ticks.py notes --repo "$(GH_REPO)" --roster "$(AUDIT_OUT)/roster.json" --notes-dir "$(AUDIT_OUT)/notes"

audit-ticks-post: ## Post each rendered supersession note once per issue; marker-idempotent, never edits an issue body (AUDIT_OUT=) — issue #2631
	python3 scripts/audit_acceptance_ticks.py post --repo "$(GH_REPO)" --roster "$(AUDIT_OUT)/roster.json" --notes-dir "$(AUDIT_OUT)/notes"

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
run-failure-reactor: ## Route a failed CI run to a remedy (issue #286): a PR this bot can push (this repo, or the owner's fork) -> dispatch the fix-bot with github.token (GH_TOKEN); else file ONE deduped issue labelled agent:implement (REPO=; RUN_ID=; DRY=1 previews)
	@test -n "$(REPO)" || { echo "Usage: make run-failure-reactor REPO=<owner/repo> RUN_ID=<run> [DRY=1]"; exit 1; }
	@test -n "$(RUN_ID)" || { echo "Usage: make run-failure-reactor REPO=<owner/repo> RUN_ID=<run> [DRY=1]"; exit 1; }
	python3 scripts/run_failure_reactor.py --repo "$(GH_REPO)" --run-id "$(RUN_ID)" $(if $(DRY),--dry,)

implement-issue: ## Implement issue.md with Hermes INSIDE the agent image (AGENTS.md is the authority; NOUS_API_KEY/GH_TOKEN from secrets; runs the gates; pushes nothing); the transcript is REDACTED before it prints (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  -e NOUS_API_KEY -e GH_TOKEN -e HERMES_REASONING -e REPO \
	  -e TYPESAFE_API_KEY \
	  -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _implement-issue')
	$(MAKE) --no-print-directory agent-repo-ownership
	$(MAKE) --no-print-directory issue-bot-pr-body-check ISSUE=$(if $(ISSUE),$(ISSUE),$(shell echo "$(BRANCH)" | sed -n 's|^agent/issue-\([0-9]*\).*|\1|p'))

agent-repo-ownership: ## Give the mounted checkout back to the invoking user after a containerized agent leg (a root-run leg leaves `.git/objects` unwritable, so the next `git add` dies with "insufficient permission"; issue #770)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm -v "$(OWNERSHIP_DIR):/repo" --entrypoint chown \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) -R $(shell id -u):$(shell id -g) /repo)

issue-bot-pr-body-check: ## CI: refuse the agent's pr-body.md before the leg spends its gates on a body that cannot become a PR (a missing or empty Issue:/Fix:/Benefit:/Technical: part; issue #770)
	@test -f $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) || { echo "[issue-implementer] no $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) was written - the leg cannot open a PR without it (issue #770)"; exit 1; }
	python3 scripts/issue_implementer.py check-body --body-file $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) $(if $(ISSUE),--issue $(ISSUE),)

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

_implement-issue: # (internal) the host recipe: implement issue.md with Hermes. Invoked
# inside the agent image by the public `implement-issue` target.
	$(MAKE) _agent-jev-preflight
	hermes -z "Follow the preloaded skill issue-implement. Its Input is issue.md; leave the change uncommitted in /repo and write pr-body.md at the repo root." -s issue-implement,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo
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
bots-restore-health: ## The #902 restore condition, as a measurement — guard that no never-pause workflow is `disabled_manually`, and report the ordered restore list once the queue is healthy (issue #902/#817; REPO= slug, CMD= restore|measure)
	python3 scripts/bots_restore_health.py "$(if $(CMD),$(CMD),restore)" $(if $(REPO),--repo "$(GH_REPO)",)
targets-coverage: ## Print every Makefile target with the callers found (workflow step, script reference, or none), marking `_`-prefixed targets internal, so "which targets does nothing run" is a measurement (issue #1102)
	python3 scripts/targets_coverage.py
issue-cleaner-scan: ## Which OPEN issue a merged PR already implemented (the linkage guard cannot see, issue #325): prints each finding and its evidence, closes nothing (REPO= picks the repo)
	python3 scripts/issue_cleaner.py --repo "$(GH_REPO)" --dry
issue-cleaner-apply: ## Close the issues a merged-to-main PR implemented but left open, each with a comment citing the PR (issue #325; the stale-branch cleanup workflow runs this daily, issue #1414; REPO= picks the repo)
	python3 scripts/issue_cleaner.py --repo "$(GH_REPO)"
worktree-report: ## Report every worktree with its branch, merged-into-main, open PR, dirty state, ahead/behind and uncommitted paths; a workspace lane prints the primary checkout's parked branch so the spawn defect is visible before it seeds the next worktree; mutates nothing and deletes nothing (issues #794, #845); SLUG= picks the repo gh reads, BASE= the base ref
	python3 scripts/worktree_report.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main)
worktree-base: ## Resolve the base a worktree MUST be cut from — `refs/remotes/origin/main`, fetched first, NEVER the primary checkout's HEAD (issue #845); ADD=1 PATH= DIR= BRANCH= passes the resolved base to `git worktree add` so the dispatch seam cuts from origin/main regardless of what the primary checkout is parked on
	@python3 scripts/worktree_base.py $(if $(ADD),add --path "$(PATH)" --branch "$(BRANCH)",resolve)
worktree-prune: ## Remove the worktrees and branches whose work landed on the base — proven by the PR's merge commit OR by ancestry, and held back by any OPEN PR or OPEN issue the branch names (issues #431, #2262); DRY=1 prints the plan, BASE= picks the base ref, SLUG= the owner/name gh reads; an UNATTENDED run — CI, BOT, or the dispatcher's HERMES_KANBAN_* — is REFUSED unless CONFIRM=1 (issue #794)
	@python3 scripts/worktree_prune_guard.py
	python3 scripts/worktree_prune.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main) $(if $(DRY),--dry,)
queued-alarm: ## Report jobs stuck in `queued` far too long (a runner that never picks them up, issue #254); COMMENT=1 delivers the report, DRY=1 previews it
	python3 scripts/queued_run_alarm.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(COMMENT),--comment,) $(if $(DRY),--dry,)
check-zero-job-pending: ## Fail when a dispatched run has been pending/queued longer than MINUTES with ZERO jobs instantiated (none named it: queued-alarm scans job rows, reactor needs a conclusion; issue #1410); FILE=1 files ONE deduped issue per stuck run, CANCEL=1 also CANCELS every stranded run (re-reads its jobs first — a run whose runner finally arrived is skipped, never killed; issue #1410 + 2026-11-12 zombie-queue measurement)
	python3 scripts/check_zero_job_pending.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(filter 1,$(FILE)),--file,) $(if $(filter 1,$(CANCEL)),--cancel-stranded,)
stale-branch-cleanup: ## Delete non-main branches older than 3 days with no open PR and fully delivered commits (issue #1344); APPLY=1 deletes, default report-only, AGE_DAYS overrides
	python3 scripts/stale_branch_cleanup.py --repo $(GH_REPO) --age-days $(if $(AGE_DAYS),$(AGE_DAYS),3) $(if $(filter 1,$(APPLY)),--apply,)
sweep-concurrency-report: ## Report every scheduled workflow whose runs stack instead of superseding, with the measurement and the decision each one needs (issue #917)
	python3 scripts/sweep_concurrency.py report


fix-loop-image: ## Run the fix-bot loop inside the agent image (the same image the workflow uses); AGENT_IMAGE overrides the resolved ref, LOG=path also receives the REDACTED log (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	$(call scrubbed_run,img=$$(if [ -n "$(AGENT_IMAGE)" ]; then echo "$(AGENT_IMAGE)"; else python3 scripts/ci_images.py latest agent; fi); echo "agent image: $$img"; $(RUNTIME) run --rm --init -v "$$PWD:/repo" -w /repo -e NOUS_API_KEY -e GH_TOKEN -e FIX_CHECK -e FIX_ROUNDS -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) "$$img" bash -lc 'scripts/agent_jev_preflight.sh && FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh'; $(if $(LOG),cp -f $(HERMES_LOG_SCRUBBED) $(LOG),true))

fix-bot-sweep: ## Which red PR the fix-bot should repair, and dispatch it (DRY=1 previews; needs gh)
	python3 scripts/fix_bot_sweep.py --repo $(GH_REPO) --check "$(if $(CHECK),$(CHECK),make ci-unit)" --max-attempts $(if $(ATTEMPTS),$(ATTEMPTS),5) $(if $(OWN_FORK),--own-fork $(OWN_FORK),) $(if $(PR),--pr $(PR),) $(if $(REPORT_FILE),--report-file "$(REPORT_FILE)",)$(if $(DRY),--dry,)

fix-bot-report: ## Render the fix-bot's failure report from the loop's report file (REPORT=<path>; the same command the workflow uses to comment)
	python3 scripts/fix_bot_report.py "$(if $(REPORT),$(REPORT),/tmp/fix-report.txt)" --command "$(if $(CHECK),$(CHECK),make ci-unit)"

agent-image-ref: ## Print the GHCR :latest ref every agent pull uses (publish points it at the content hash)
	@python3 scripts/ci_images.py latest agent

fix-loop: ## Run the PR fix-bot loop locally against the failing check (scripts/fix_loop.sh; needs an agent on PATH)
	FIX_ROUNDS="$(if $(ROUNDS),$(ROUNDS),5)" FIX_CHECK="$(if $(CHECK),$(CHECK),make ci-unit)" FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh


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

auto-merge: ## Merge a PR ONLY when this run is green and the PR is conflict-free: state OPEN, mergeable MERGEABLE, mergeStateStatus CLEAN (no conflicts, not behind, not blocked), head pinned to HEAD_SHA, no do-not-merge label; then verify what it closed (PR= REPO= HEAD_SHA= from ci.yml; APPROVE=1 approves a green review-blocked PR with the other allowed identity; DRY=1 prints the decision)
	@test -n "$(PR)" && test -n "$(REPO)" || { echo "Usage: make auto-merge PR=<n> REPO=<owner/repo> [HEAD_SHA=<sha>] [APPROVE=1] [DRY=1]"; exit 1; }
	python3 scripts/auto_merge.py auto-merge --repo "$(GH_REPO)" --pr $(PR) $(if $(HEAD_SHA),--head-sha $(HEAD_SHA),) $(if $(APPROVE),--approve-when-review-required,) $(if $(ACTOR),--actor $(ACTOR),) $(if $(DRY),--dry,)
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
.PHONY: check-merge-on-red alert-merged-red stacked-merge-detect

# A bot's review VERDICT is a comment marker, never an approval (issue #852): every bot pushes with the
# owner's token, so `gh pr review --approve` on its own PR is refused and `reviewDecision` can never leave
# REVIEW_REQUIRED. The marker names the head it reviewed, and `auto_merge.decide()` accepts it ONLY at the
# PR's current head — a stale verdict counts for nothing. One producer, one format: scripts/bot_verdict.py.
bot-verdict: ## Post a bot review verdict at one head on a PR (a marker comment, never an approval; deduped per head+verdict): VERDICT=approve|changes HEAD=<sha> RUN=<run id> REPO= PR= [REVIEWER=] [NOTE=] [DRY=1] (issue #852); RUN is the Actions run id that measured that head (#1551)
	@test -n "$(HEAD)" && test -n "$(REPO)" && test -n "$(PR)" && test -n "$(VERDICT)" && test -n "$(RUN)" || { echo "Usage: make bot-verdict VERDICT=approve|changes HEAD=<full sha> RUN=<run id> REPO=<owner/repo> PR=<n> [REVIEWER=<login>] [NOTE=] [DRY=1]"; exit 1; }
	python3 scripts/bot_verdict.py post --repo "$(GH_REPO)" --pr $(PR) --head "$(HEAD)" --run "$(RUN)" --verdict "$(VERDICT)" $(if $(REVIEWER),--reviewer "$(REVIEWER)",) $(if $(NOTE),--note "$(NOTE)",) $(if $(DRY),--dry,)
bot-verdict-read: ## Print the bot verdict the merge gate would read for a PR at its current head (REPO= PR= [HEAD=])
	@test -n "$(REPO)" && test -n "$(PR)" || { echo "Usage: make bot-verdict-read REPO=<owner/repo> PR=<n> [HEAD=<sha>]"; exit 1; }
	python3 scripts/bot_verdict.py show --repo "$(GH_REPO)" --pr $(PR) $(if $(HEAD),--head "$(HEAD)",)
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
check-arms: # internal alarm plumbing (rule 16 consumer) — stays out of the user-facing docs; its scheduled workflow arms.yml is the caller
	python3 scripts/check_arms.py check
arms-report: # internal alarm plumbing (rule 16 consumer) — stays out of the user-facing docs
	python3 scripts/check_arms.py report

arm-auto-merge: ## Arm auto-merge on every open PR that is not a draft and not already armed (AUTHOR= limits it to one lane; DRY=1 calls nothing — issue #912)
	python3 scripts/arm_auto_merge.py arm $(if $(AUTHOR),--author "$(AUTHOR)",) $(if $(DRY),--dry,)
arm-auto-merge-report: ## Show the open PRs that carry no auto-merge intent yet, with their author and mergeable state (issue #912)
	python3 scripts/arm_auto_merge.py report $(if $(AUTHOR),--author "$(AUTHOR)",)
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


# Native (non-container) engine tests are hardware-scoped (issue #114): only Metal runs
# natively, so they have test cases only on an Apple-Silicon Mac. On any other host
# (every Linux CI job, cuda/rocm/vulkan/cpu) these targets have no case for that
# hardware and say so; the Linux engines are tested through their images instead.
# NATIVE_HOST= simulates a non-Metal host.
NATIVE_HOST ?= $(shell [ "$$(uname -s)-$$(uname -m)" = "Darwin-arm64" ] && echo metal)
NATIVE_GUARD = [ "$(NATIVE_HOST)" = "metal" ] || { echo "[$@] native engines are Metal-only: this host ($$(uname -s) $$(uname -m)) has none; its engines are tested in their images (make test-engine)"; exit 0; };


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

