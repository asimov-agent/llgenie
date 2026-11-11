# mk/gates.mk — the host / gate / coverage / lint domain of the top Makefile (issue #800 → #2457).
#
# Moved BYTE-IDENTICAL from the top Makefile (issue #800 decomposition): `include mk/gates.mk` in the
# top Makefile brings them back. No recipe changed; only the file that declares each target moved.


bash-check:
	@python3 scripts/check_bash.py "$(SHELL)" $(if $(CHECK_BASH_FORCE),--force,)

# Put ~/bin on PATH for every recipe so `llama-server` (symlinked there by
# `make install`) resolves even in non-interactive make subprocesses — not just
# in an interactive zsh that sourced ~/.zshrc.

check-agent-model: ## CI: fail when the agent image's model pin (Dockerfile ARG, install script) is not the one snapshot scripts/agent_model_pin.py declares — or the alias's budget is missing (issue #405)
	python3 scripts/agent_model_pin.py check


model-pin-report: ## Print the bots' pinned model snapshot, where each place declares it, and every finding (issue #405)
	python3 scripts/agent_model_pin.py report

# ---- every bot leg loads its contract from a project skill (issue #577) --------------
# A leg's inline prompt used to be its whole rulebook (1005-1629 characters, the same
# UNATTENDED paragraph seven times). The contract is a Hermes project skill now -
# .hermes/skills/<name>/SKILL.md, the layout Hermes discovers from a trusted checkout - and
# the leg preloads it with `hermes -s <name>`. The gate fails a leg that preloads nothing,
# names a skill that does not exist, carries a name that disagrees with its directory, grows
# past the pointer budget, or inlines the unattended contract again.

check-import-roots: ## CI: fail when a test file carries its own `sys.path` entry or imports a `scripts/` module bare — a ratchet against the recorded counts (issue #796)
	python3 scripts/check_import_roots.py ratchet

check-package-layers: ## CI: fail on an import cycle in scripts/, a cross-group import the layering data does not state, a stated edge the tree no longer has, or a module no group places (scripts/package-layers.json, issue #795)
	python3 scripts/check_package_layers.py check


check-agent-profiles-ratchet: ## CI: refuse committed-tree findings past the recorded baseline (tests/fixtures/agent-profiles-baseline.json) — live-alone drift is excluded so a clean lane greens on a drifted host, but the fleet tree cannot rot silently (issue #1090)
	python3 scripts/check_agent_profiles.py --ratchet


check-agent-skills: ## CI: fail when a bot leg does not preload its project skill, names a missing one, or carries a rulebook inline instead of a pointer (issue #577)
	python3 scripts/check_agent_skills.py check


agent-skills-report: ## Print every agent leg with its prompt size and preloaded skills, and every skill with its frontmatter (issue #577)
	python3 scripts/check_agent_skills.py report


check-skill-code-parity: ## CI: fail when a skill reference (<profile>/skills/**/*.md) cites a test id (`tests/x.py::test_y`) whose test is not in the hermetic suite, or names a repository-owned code symbol that does not resolve — the documented mechanism must match the code (issue #1924, Layer B)
	python3 scripts/check_skill_code_parity.py check


check-agent-profiles: ## CI: fail when a listed host-agent profile has no SOUL.md, a skill's frontmatter name disagrees with its directory, a skill names a missing reference, exceeds the 100,000-character skill-writer limit, or carries a secret value, a SOUL.md dropped a standing rule — searched in the file's own voice, so a QUOTED rule satisfies nothing — or a file, or a whole skill directory, exists only in the live profile with no counterpart in the tree (issue #791, #922, #1069, #1086, #2084)
	python3 scripts/check_agent_profiles.py check


agent-profiles-report: ## Print every host-agent profile with its SOUL.md size, its skills and its standing rules, then every finding (issue #791)
	python3 scripts/check_agent_profiles.py report


# ---- a leg refuses to start on a missing key (issue #363) --------------------
# A leg that forwards a key its job never set spends the runner first: it pulls the image,
# starts a container, and fails inside Hermes — a 120-180 minute-timeout job lost to a
# plumbing mistake, and a log that reads like a model problem. The guard runs BEFORE
# `ci_images.py ensure agent`, prints the NAME only, and exits 2 (never a skip). The key list
# per leg is the one that leg actually forwards; the suite derives the roster from this file,
# so a new leg without a guard fails the test.

check-dispatch-forms: ## CI: fail when a dispatchable workflow does not state the work it will do: name, documented dispatch inputs, header block, and the docs/BOTS.md table
	python3 scripts/check_dispatch_forms.py check

dispatch-forms-report: ## Print the dispatch table in docs/BOTS.md (generated from the workflow files; paste it between the dispatch-forms markers)
	python3 scripts/check_dispatch_forms.py report

check-wiring: ## CI: fail when a test/script is wired to no make target or only to one CI never runs, when a recorded host-only exception is stale, when a workflow calls a make target that does not exist, or when a `.PHONY` entry names no target or a target that runs nothing (issue #883)
	python3 scripts/check_wiring.py check

wiring-report: ## Show how every test/script is wired (which make target, and whether CI runs it) and the recorded host-only exceptions
	python3 scripts/check_wiring.py report

check-docs: ## CI: fail when a user-facing (## help) make target is undocumented, a recorded exception is stale, an agent-wiki/ note references no issue or has no index row in docs/changes.d/, or README.md carries change history (issues #257, #678, #934)
	python3 scripts/changes_index.py check
	python3 scripts/check_docs.py check
	python3 scripts/check_architecture_census.py check

check-empty-files: ## CI: fail when a tracked or diff-added path is a zero-byte non-sentinel file (issue #1509) — a `.wt-probe.txt`-class empty diagnostic must never ride a squash to main again; `.gitkeep`-style sentinels are the only allowed empty case. Uses the added-paths gate against `origin/main` when the base resolves (the PR and main-push case — scope.yml fetches it), else the present-empties scan (a bare local checkout)
	@if git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then \
	    python3 scripts/check_empty_files.py check --base origin/main; \
	else \
	    python3 scripts/check_empty_files.py check --all; \
	fi

check-architecture-census: ## CI: fail when the docs/ARCHITECTURE.md census disagrees with the tree at the `measured at <sha>` commit it names (which must be an ancestor of HEAD), naming both values and the sha measured (issues #896, #1053)
	python3 scripts/check_architecture_census.py check

check-file-hygiene: ## CI: fail when a committed file matches a runtime-artifact shape — any `*.log`, or a dot-prefixed `.<word><digits>.<ext>` scratch name (e.g. `.pr874.md`) — unless a dated exception records why (issue #2484); lists findings as paths only
	python3 scripts/check_file_hygiene.py check
file-hygiene-report: ## Show every committed `*.log` / dot-scratch artifact and every stale exception the hygiene gate reads, plus the dated exception fixture that records the intentional ones (issue #2484)
	python3 scripts/check_file_hygiene.py report

.PHONY: check-file-hygiene
.PHONY: file-hygiene-report

docs-report: ## Show every user-facing make target as documented / missing / a recorded exception, and each agent-wiki/ note's issue references + its docs/changes.d/ index row
	python3 scripts/check_docs.py report

changes-index: ## Render CHANGES.md from the one-row-per-change files in docs/changes.d/ (never edit CHANGES.md by hand; one row per file is what keeps two open PRs from conflicting — issue #934)
	python3 scripts/changes_index.py write

changes-index-report: ## Show the docs/changes.d/ fragment census and how many rows CHANGES.md is behind them
	python3 scripts/changes_index.py report

changes-resolve: ## Repair a CHANGES.md merge conflict: take BASE's file (default origin/main) and re-render from the merged fragments, then stage it (issue #1103; BASE=<ref>)
	python3 scripts/changes_index.py resolve --base "$(if $(BASE),$(BASE),origin/main)"

check-pr-hygiene: ## CI: fail when a producer's commit message or PR body is empty, a placeholder, a subject with no body, or when AGENTS.md lost the mandate (issue #313); also fail when a CHANGES.md row has no docs/changes.d/<stem>.md fragment or a note appears twice (issue #1063)
	python3 scripts/check_pr_hygiene.py check
	python3 scripts/check_pr_hygiene.py changes-index

check-pr-agents-line: ## CI: fail when a bot PR's body omits or mis-cites the `AGENTS:` line (and its `BASE:` companion) whose rulebook is not reachable from both head and base (issues #792, #845) — the #792 AGENTS-preflight; the guard jobs call it with the LIVE PR body (same fetch as check-pr-closing, issue #1589), never from a hermetic chain
	python3 scripts/check_pr_hygiene.py agents-line --head "$(if $(PR_HEAD),$(PR_HEAD),HEAD)" --base "$(PR_BASE)" --body-file "$(PR_BODY)"

check-pr-sync-line: ## CI: fail when a profile-editing bot PR (a diff under agents/<profile>/) does not report its live re-sync in a `SYNC:` line — the owner's profile-propagation rule (issue #1724); the guard jobs call it with the LIVE PR body, never from a hermetic chain
	python3 scripts/check_pr_hygiene.py sync-line --head "$(if $(PR_HEAD),$(PR_HEAD),HEAD)" --base "$(PR_BASE)" --body-file "$(PR_BODY)"

check-pr-openspec-change: ## CI: fail when an implementing bot PR's final diff adds no `openspec/changes/<name>/` file and its body names no ACTIVE change it implements against (`OPENSPEC: <name>`) — the presence half #1807 (AGENTS.md MANDATORY change-first; `ci-openspec` only iterates EXISTING changes, so an openspec-empty implementing PR is otherwise CI-green); the guard jobs call it with the LIVE PR body, never from a hermetic chain. Reuses the existing openspec gates (openspec-validate-all / openspec-tasks-check own structure and ticks) — never weakened
	python3 scripts/check_pr_hygiene.py openspec-change --head "$(if $(PR_HEAD),$(PR_HEAD),HEAD)" --base "$(PR_BASE)" --body-file "$(PR_BODY)"

check-pr-acceptance-form: ## CI: fail when a bot PR's body carries no own `## Acceptance criteria` `- [ ]` checklist — the owner's universal form rule (issue #1796): every issue a lane files AND every PR body it opens has a tickable acceptance section; verification/surface only, never a #1088 merge-blocker, never a tick (that stays #1644); the guard jobs call it with the LIVE PR body, never from a hermetic chain
	python3 scripts/check_pr_hygiene.py acceptance-form --head "$(if $(PR_HEAD),$(PR_HEAD),HEAD)" --base "$(PR_BASE)" --body-file "$(PR_BODY)"

check-pr-acceptance: ## CI: fail when a merged PR closes an issue whose `## Acceptance criteria` carries an unmarked `- [ ]` item, or when the PR body ticks a criterion the linked issue still has unchecked (issue #1792) — verification only, it never ticks boxes (that stays #1644, the verdict-gated write-back); the guard jobs call it with the LIVE PR body (same fetch as check-pr-closing, issue #1589) and the LIVE linked issue at merge time, and with the squash commit range (PR_BASE/PR_HEAD) so a `(closes #N)` that lives ONLY in the squash text GitHub's native close reads is held too (issue #1815); with PR_NUMBER it reads the LIVE trusted verdict trail on that PR, so a criterion proven by an approve verdict at the current head reports `proven-awaiting-writer` instead of red (issue #2187)
	python3 scripts/check_pr_acceptance.py check --body-file "$(if $(PR_BODY),$(PR_BODY),/dev/null)" $(if $(PR_BASE),--base "$(PR_BASE)",) --rev "$(if $(PR_HEAD),$(PR_HEAD),HEAD)" $(if $(PR_NUMBER),--pr "$(PR_NUMBER)",)

check-pr-acceptance-body: ## CI: fail when a PR whose OWN `## Acceptance criteria` checklist is the SOLE vehicle for its acceptance record (an engine-bump PR that closes no issue, #2352) carries an unticked `- [ ]` box at its current head, or a `- [x]` box naming no re-producible run id / command+rc+sha — so auto-merge cannot arm on a ci-verdict that ignored an unticked box (measured #2267 merged 0/4 unticked with the pin unpublished at head); verification only, it ticks nothing; a PR that closes an issue is left to the issue-side `check-pr-acceptance`, and absence of a checklist to `check-pr-acceptance-form`; the guard jobs call it with the LIVE PR body (same fetch as check-pr-closing, issue #1589), never from a hermetic chain
	python3 scripts/check_pr_acceptance.py body --body-file "$(if $(PR_BODY),$(PR_BODY),/dev/null)" $(if $(PR_BASE),--base "$(PR_BASE)",) --rev "$(if $(PR_HEAD),$(PR_HEAD),HEAD)"

pr-hygiene-report: ## Show every producer the PR/commit-message guard reads, and its verdict
	python3 scripts/check_pr_hygiene.py report

check-pr-closing: ## CI: fail when a claimed issue lacks an adjacent closes/fixes/resolves #N in the joined commit messages and, when the body is supplied, in the PR body, or when an agent/* body names an issue with no adjacent keyword (issues #1329, #1417)
	python3 scripts/check_pr_closing.py check $(if $(PR_BODY),--body-file "$(PR_BODY)",) $(if $(PR_BRANCH),--head "$(PR_BRANCH)",) --base "$(PR_BASE)" --rev HEAD

check-pr-base: ## CI: fail when a PR's merge-base with the base ref is not the base itself — a branch cut from another PR leaks that PR's diff under its own closes; name the foreign commit (issue #845); PR_BASE= the base ref a PR must be cut from (default origin/main, the shared default check-pr-closing uses; the ci.yml guard step and pipeline unit job set it explicitly and fetch it live), PR_HEAD= the head rev (default HEAD — the unit job sets no PR_HEAD, so HEAD is the branch being built), PR_BRANCH= the PR's head branch name and PR_NUMBER= the PR number, so the branch's own refs are OWN even when HEAD is the PR merge ref (issue #2138)
	python3 scripts/check_pr_base.py check --base "$(PR_BASE)" --rev "$(if $(PR_HEAD),$(PR_HEAD),HEAD)" $(if $(PR_BRANCH),--head-ref-name "$(PR_BRANCH)",) $(if $(PR_NUMBER),--pr-number "$(PR_NUMBER)",)

pr-closing-report: ## Show the closing references a PR body carries, the squash closes, and whether the agent/* scope applies (issues #1329, #1417)
	python3 scripts/check_pr_closing.py report $(if $(PR_BODY),--body-file "$(PR_BODY)",) $(if $(PR_BRANCH),--head "$(PR_BRANCH)",) --base "$(PR_BASE)" --rev HEAD

check-proc-gate: ## CI: fail when a subprocess.run/check_output/Popen appears in scripts/ outside scripts/proc.py or a `# proc-allow:` line — the ONE subprocess policy seam (issue #797)
	python3 scripts/check_proc_gate.py check

proc-gate-report: ## Show the census of every direct subprocess.* call site in scripts/, allow-listed or bare — the tracked remainder that must shrink onto scripts/proc.py (issue #797)
	python3 scripts/check_proc_gate.py report

check-report-hygiene: ## CI: fail when a reporting leg blames ownership (another lane, someone else, this lane) without a @<sha> evidence anchor — evidence-or-silence (issue #1292)
	python3 scripts/check_report_hygiene.py check

report-hygiene-report: ## Show every reporting leg the ownership-guard reads and its verdict
	python3 scripts/check_report_hygiene.py report

check-report-header: ## CI: fail when a reporting leg emits a status header missing one of the six fields (`BOT <name>` · `working on #<id>` · `branch <ref>` · `since <hh:mmZ>` · `blocked on <x|none>` · `next <y>`) — a report without an id, a branch or a run id is not a report (issue #1615)
	python3 scripts/check_report_header.py check

report-header-report: ## Show every reporting leg the header-guard reads and its verdict
	python3 scripts/check_report_header.py report

check-pr-heads: ## Warn (never fail) when an open PR's head lives in another repository, naming it with the reason and the remedy (issue #910)
	python3 scripts/pr_heads.py check

pr-heads-report: ## Show every open PR grouped by head repository, with the same-repo rule and why it is the rule (issue #910)
	python3 scripts/pr_heads.py report

check-issue-bodies: ## CI: fail when a producer hand-builds an issue body, a body misses a section or puts `## Technical` anywhere but last, an acceptance criterion is absent, or AGENTS.md / the issue skills lost the rule (issue #745)
	python3 scripts/check_issue_body.py check

issue-bodies-report: ## Show every issue producer, whether it renders through the one seam, the section order and the verdict
	python3 scripts/check_issue_body.py report
# BASE/HEAD bound the commit range the guard reads (defaults: origin/main..HEAD). ci-unit runs it with
# no range, so the static half (AGENTS.md + the producers) is still checked on a push to main; a PR
# run reads the commits the PR adds.

check-pr-authors: ## CI: fail when a PR's commit is authored through an allowlisted email address, when a Co-authored-by trailer names anyone else, or when a producer commits off the allowlist (issue #345)
	python3 scripts/check_pr_authors.py check --base "$(PR_BASE)" --head "$(PR_HEAD)"

pr-authors-report: ## Show every commit in the range with its author verdict, and the identity each producer assigns
	python3 scripts/check_pr_authors.py report --base "$(PR_BASE)" --head "$(PR_HEAD)"
# The ONE source of the identity every leg commits as (issue #840). `git-identity-apply` writes the
# allowlisted pair into THIS repository's git config — the one place a leg sources it from, instead of
# nine literals in three spellings, or whatever the host's ~/.gitconfig happens to hold.
# `check-git-identity` fails when the identity git would actually use is outside
# `scripts/check_pr_authors.py::ALLOWED`, naming where it came from (GIT_AUTHOR_EMAIL, a config file).
# `git-identity-line` is the `Author:` line a bot's PR body carries. All three are CI/leg plumbing, so
# none carries a `##` help line: `make help` documents what a USER runs.

git-identity-apply:
	python3 scripts/git_identity.py apply

check-git-identity:
	python3 scripts/git_identity.py check

git-identity-line:
	@python3 scripts/git_identity.py line

git-identity-report:
	python3 scripts/git_identity.py report

check-workflows: ## CI: fail when a YAML file's GitHub expression does not parse, when a YAML file lacks a trailing newline, when a workflow has no top-level name, or when a `workflow_run` roster names a workflow that does not exist or leaves one unwatched (issues #330, #349)
	python3 scripts/check_workflows.py check

workflows-report: ## Show every YAML file the workflow gate reads, how many expressions it validated, and its verdict
	python3 scripts/check_workflows.py report

check-module-names: ## CI: fail when a LIVE file spells the retired CLI module name instead of scripts/llgenie_serve.py (the old spelling belongs to the deprecated shim and the dated history only; issues #251, #573, #812)
	python3 scripts/module_name_guard.py check

check-claim-reader: ## CI: fail when a LIVE file re-opens the run-liveness read outside scripts/bot_claims.py (the claim protocol is ONE reader; issues #799)
	python3 scripts/claim_reader_guard.py check

openspec-image: ## The OpenSpec CLI image: pull the published hash of openspec/Dockerfile (GHCR), else build it here (issue #117)
	python3 scripts/ci_images.py ensure openspec


openspec-image-pull: ## The OpenSpec CLI image: strict pull of the published hash (openspec/Dockerfile) as $(OS_IMG); fails if not published, never builds — a host-side helper now that the openspec gates call make openspec-image (issue #1673)
	python3 scripts/ci_images.py pull openspec


openspec-new: openspec-image ## openspec new change <NAME>
	@test -n "$(NAME)" || { echo "Usage: make openspec-new NAME=<kebab-name>"; exit 1; }
	$(RUNTIME) run $(OS_OPTS) openspec new change $(NAME)


openspec-validate-all: ## openspec validate --changes: verify the STRUCTURE of every ACTIVE change (the gate a commit's own change cannot slip past, issue #156)
	@if [ "$(HOST_OS)" = Darwin ]; then \
	  command -v openspec >/dev/null 2>&1 || npm install -g @fission-ai/openspec@$(OPENSPEC_VERSION); \
	  openspec validate --changes; \
	else $(RUNTIME) run $(OS_OPTS) openspec validate --changes; fi

openspec-validate: ## openspec validate <NAME>  (fail-closed gate used by the loop)
	@test -n "$(NAME)" || { echo "Usage: make openspec-validate NAME=<change>"; exit 1; }
	@if [ "$(HOST_OS)" = Darwin ]; then \
	  command -v openspec >/dev/null 2>&1 || npm install -g @fission-ai/openspec@$(OPENSPEC_VERSION); \
	  openspec validate $(NAME); \
	else $(RUNTIME) run $(OS_OPTS) openspec validate $(NAME); fi


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
# The checkout, as a path. A bot job exports REPO as the slug (`asimov-agent/llgenie`) for the sweep
# and the push, and Make treats that environment variable as an override of `REPO :=` above — so a
# gate that mounts $(REPO) hands docker the slug and docker refuses it (run 39727049030: `create
# asimov-agent/llgenie: includes invalid characters for a local volume name`). A mount needs a path.
# `override` ignores the environment; the slug stays available to the bot targets through $(REPO).

lint: ## Lint: fail closed if any tracked text file lacks a trailing newline, or a markdown heading is not preceded by a blank line
	$(TEST_RUN) python scripts/lint_linefeeds.py


lint-fix: ## Append a missing trailing newline (containerized)
	$(TEST_RUN) python scripts/lint_linefeeds.py --fix


check-host-space: ## Host: refuse a /tmp worktree or container build when the shared tmpfs is below the headroom threshold (<20% space OR <50k inodes free) — the planner's preflight before dispatch (issue #1583)
	python3 scripts/check_host_space.py check

reclaim-tmp-worktrees: ## Host: reclaim /tmp worktree and probe-tree debris that is provably safe to delete — a tree is removed only when it is clean AND its HEAD is an ancestor of origin/main AND idle >= MIN_IDLE_MIN (issue #2141); DRY=1 by default and deletes/pins NOTHING (DRY=0 to act), FORCE=1 drops the on-main + idle tests but NEVER the dirty refusal and pins every novel head as refs/reclaimed/<name> before forced removal; SCAN_ROOT=/REPO=/MIN_IDLE_MIN=/BASE=/FORCE= override; root-owned leftovers are reported with the `sudo rm -rf <path>` remedy, never retried
	@REPO="$${REPO:-$$HOME/repository/git/llgenie}" SCAN_ROOT="$${SCAN_ROOT:-/tmp}" MIN_IDLE_MIN="$${MIN_IDLE_MIN:-60}" DRY="$${DRY:-1}" FORCE="$${FORCE:-0}" BASE="$${BASE:-origin/main}" bash scripts/reclaim_tmp_worktrees.sh
