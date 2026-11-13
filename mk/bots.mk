# mk/bots.mk — bot-domain targets split out of the top Makefile (issue #2460).
# Target names and recipes are byte-identical; shared variables stay in the top Makefile.

rebase-bot-sweep: ## Which ONE open PR needs rebasing (BEHIND/DIRTY against main): prints action/pr/head_* and the reason for every pass-over
	python3 scripts/rebase_bot_sweep.py --repo $(GH_REPO) $(if $(OWN_FORK),--own-fork $(OWN_FORK),) $(if $(SKIP),--skip "$(SKIP)",)

bot-preflight: ## Fetch origin/main, fast-forward a behind checkout, and record the AGENTS.md this run is measured against (issue #792); when the working diff touches agents/<profile>/, surfaces the #1724 SYNC-line obligation (BODY=<prospective PR body> refuses a missing/mis-cited SYNC line, issue #1782)
	python3 scripts/bot_preflight.py $(if $(CHECK),--check,) $(if $(BODY),--body-file "$(BODY)",)

bot-stamp-body: ## Stamp BODY=<pr body file> in place (or into OUT=) with the `AGENTS:`/`BASE:` pair measured at origin/main — the ONE stamp authority every bot PR producer calls before `gh pr create`/`gh pr edit`, so a bot PR never opens unstamped (issue #2050); BASE=/REFS= name the main ref a producer's checkout actually stands on
	@test -n "$(BODY)" || { echo "Usage: make bot-stamp-body BODY=<pr body file> [OUT=<file>] [BASE=origin/main] [REFS=origin/HEAD,main]"; exit 1; }
	python3 scripts/bot_preflight.py --stamp "$(BODY)" $(if $(OUT),--out "$(OUT)",) $(if $(BASE),--base "$(BASE)",) $(if $(REFS),--refs "$(REFS)",)

check-tick-prompt: ## Fail when the live orchestrator cron prompt diverges from the versioned copy under agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md (issue #2159) — host-only: a CI runner has no live jobs.json; exit 0 identical, 1 diverged, 2 a read/missing failure (LIVE=; VERSIONED=), HOST-ONLY
	@python3 scripts/check_tick_prompt.py $(if $(LIVE),--live "$(LIVE)",) $(if $(VERSIONED),--versioned "$(VERSIONED)",)

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

issue-bot-gates: ## Run the FAST repository gates in order, stopping at the FIRST failure and naming it (lint, workflows, wiring, docs, PR hygiene, OpenSpec tasks): what the issue-bot runs after the implement step and BEFORE it pushes, so a bookkeeping red never reaches the PR (issue #475)
	python3 scripts/issue_bot_gates.py run

issue-bot-gates-check: ## CI: fail when a ci-unit gate is classified neither fast nor deferred, a fast gate is unwired or not .PHONY, or the issue-bot's gate step is not between the change detection and the push (issue #475)
	python3 scripts/issue_bot_gates.py check

bot-sync-main: ## Fetch upstream main and reset the working tree to it, so a NEW branch starts from latest main (issue #303); fails loudly when main cannot be reached
	@bash scripts/bot_sync_main.sh reset

bot-sync-branch: ## Fetch upstream main and rebase the checked-out PR branch onto it before repairing (issue #303); exit 2 means the rebase conflicts and is left to the rebase-bot
	@bash scripts/bot_sync_main.sh rebase

web-coverage: ## Which URLs a bot run depends on, and do they resolve (a fixture list, or ISSUE_FILE=); non-zero on a dead one — no model call, no key
	python3 scripts/web_evidence.py check $(if $(ISSUE_FILE),$(ISSUE_FILE),tests/fixtures/bot-facing-urls.md) $(if $(URLS),--urls $(URLS),)

issue-evidence: ## Pre-fetch the URLs an issue names so the agent reviews against real text: drives the ONE `agent-fetch` leg, capped, never fatal (ISSUE_FILE=, OUTDIR=fetched, MAX=3)
	@test -n "$(ISSUE_FILE)" || { echo "Usage: make issue-evidence ISSUE_FILE=<path> [OUTDIR=fetched] [MAX=3]"; exit 1; }
	@python3 scripts/web_evidence.py fetch $(ISSUE_FILE) --outdir $(if $(OUTDIR),$(OUTDIR),fetched) --max $(if $(MAX),$(MAX),3)

code-review-scan: ## The code-review bot's checks: tree + pipelines -> findings (REPO=; STATIC=1 skips the checks that read the GitHub API; JSON=1 for machine output; no model spend, writes nothing)
	python3 scripts/code_review.py scan --repo "$(GH_REPO)" $(if $(STATIC),--static-only,) $(if $(JSON),--json,)

code-review-file: ## File ONE issue per NEW code-review finding, capped per run (REPO=; CAP= issues per run, default 3; DRY=1 previews) — never edits code, never merges
	@test -n "$(REPO)" || { echo "Usage: make code-review-file REPO=<owner/repo> [CAP=3] [DRY=1]"; exit 1; }
	python3 scripts/code_review.py file --repo "$(GH_REPO)" $(if $(CAP),--cap $(CAP),) $(if $(DRY),--dry,)

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

audit-ticks: ## Re-measure the acceptance-tick corpus over all closed issues; exit 0 only when zero unsuperseded stale ticks remain (issue #2631)
	python3 scripts/audit_acceptance_ticks.py audit --repo "$(GH_REPO)" --roster "$(AUDIT_OUT)/roster.json"

audit-ticks-notes: ## Render the supersession note bodies for the roster's remaining stale ticks (AUDIT_OUT=; append-only, ticks stay as written) — issue #2631
	python3 scripts/audit_acceptance_ticks.py notes --repo "$(GH_REPO)" --roster "$(AUDIT_OUT)/roster.json" --notes-dir "$(AUDIT_OUT)/notes"

audit-ticks-post: ## Post each rendered supersession note once per issue; marker-idempotent, never edits an issue body (AUDIT_OUT=) — issue #2631
	python3 scripts/audit_acceptance_ticks.py post --repo "$(GH_REPO)" --roster "$(AUDIT_OUT)/roster.json" --notes-dir "$(AUDIT_OUT)/notes"

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

issue-bot-pr-body-check: ## CI: refuse the agent's pr-body.md before the leg spends its gates on a body that cannot become a PR (a missing or empty Issue:/Fix:/Benefit:/Technical: part; issue #770)
	@test -f $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) || { echo "[issue-implementer] no $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) was written - the leg cannot open a PR without it (issue #770)"; exit 1; }
	python3 scripts/issue_implementer.py check-body --body-file $(if $(BODY_FILE),$(BODY_FILE),pr-body.md) $(if $(ISSUE),--issue $(ISSUE),)

_implement-issue: # (internal) the host recipe: implement issue.md with Hermes. Invoked
# inside the agent image by the public `implement-issue` target.
	$(MAKE) _agent-jev-preflight
	hermes -z "Follow the preloaded skill issue-implement. Its Input is issue.md; leave the change uncommitted in /repo and write pr-body.md at the repo root." -s issue-implement,bot-unattended $(nous-alias) --reasoning $(HERMES_REASONING) --yolo

bots-restore-health: ## The #902 restore condition, as a measurement — guard that no never-pause workflow is `disabled_manually`, and report the ordered restore list once the queue is healthy (issue #902/#817; REPO= slug, CMD= restore|measure)
	python3 scripts/bots_restore_health.py "$(if $(CMD),$(CMD),restore)" $(if $(REPO),--repo "$(GH_REPO)",)

issue-cleaner-scan: ## Which OPEN issue a merged PR already implemented (the linkage guard cannot see, issue #325): prints each finding and its evidence, closes nothing (REPO= picks the repo)
	python3 scripts/issue_cleaner.py --repo "$(GH_REPO)" --dry

issue-cleaner-apply: ## Close the issues a merged-to-main PR implemented but left open, each with a comment citing the PR (issue #325; the stale-branch cleanup workflow runs this daily, issue #1414; REPO= picks the repo)
	python3 scripts/issue_cleaner.py --repo "$(GH_REPO)"

queued-alarm: ## Report jobs stuck in `queued` far too long (a runner that never picks them up, issue #254); COMMENT=1 delivers the report, DRY=1 previews it
	python3 scripts/queued_run_alarm.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(COMMENT),--comment,) $(if $(DRY),--dry,)

check-zero-job-pending: ## Fail when a dispatched run has been pending/queued longer than MINUTES with ZERO jobs instantiated (none named it: queued-alarm scans job rows, reactor needs a conclusion; issue #1410); FILE=1 files ONE deduped issue per stuck run, CANCEL=1 also CANCELS every stranded run (re-reads its jobs first — a run whose runner finally arrived is skipped, never killed; issue #1410 + 2026-11-12 zombie-queue measurement)
	python3 scripts/check_zero_job_pending.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(filter 1,$(FILE)),--file,) $(if $(filter 1,$(CANCEL)),--cancel-stranded,)

fix-loop-image: ## Run the fix-bot loop inside the agent image (the same image the workflow uses); AGENT_IMAGE overrides the resolved ref, LOG=path also receives the REDACTED log (issue #359)
	@python3 scripts/require_env.py NOUS_API_KEY
	$(call scrubbed_run,img=$$(if [ -n "$(AGENT_IMAGE)" ]; then echo "$(AGENT_IMAGE)"; else python3 scripts/ci_images.py latest agent; fi); echo "agent image: $$img"; $(RUNTIME) run --rm --init -v "$$PWD:/repo" -w /repo -e NOUS_API_KEY -e GH_TOKEN -e FIX_CHECK -e FIX_ROUNDS -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) "$$img" bash -lc 'scripts/agent_jev_preflight.sh && FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh'; $(if $(LOG),cp -f $(HERMES_LOG_SCRUBBED) $(LOG),true))

fix-bot-sweep: ## Which red PR the fix-bot should repair, and dispatch it (DRY=1 previews; needs gh)
	python3 scripts/fix_bot_sweep.py --repo $(GH_REPO) --check "$(if $(CHECK),$(CHECK),make ci-unit)" --max-attempts $(if $(ATTEMPTS),$(ATTEMPTS),5) $(if $(OWN_FORK),--own-fork $(OWN_FORK),) $(if $(PR),--pr $(PR),) $(if $(REPORT_FILE),--report-file "$(REPORT_FILE)",)$(if $(DRY),--dry,)

fix-bot-report: ## Render the fix-bot's failure report from the loop's report file (REPORT=<path>; the same command the workflow uses to comment)
	python3 scripts/fix_bot_report.py "$(if $(REPORT),$(REPORT),/tmp/fix-report.txt)" --command "$(if $(CHECK),$(CHECK),make ci-unit)"

fix-loop: ## Run the PR fix-bot loop locally against the failing check (scripts/fix_loop.sh; needs an agent on PATH)
	FIX_ROUNDS="$(if $(ROUNDS),$(ROUNDS),5)" FIX_CHECK="$(if $(CHECK),$(CHECK),make ci-unit)" FIX_REPORT_FILE="$(REPORT_FILE)" scripts/fix_loop.sh

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

check-arms: # internal alarm plumbing (rule 16 consumer) — stays out of the user-facing docs; its scheduled workflow arms.yml is the caller
	python3 scripts/check_arms.py check

arms-report: # internal alarm plumbing (rule 16 consumer) — stays out of the user-facing docs
	python3 scripts/check_arms.py report

arm-auto-merge: ## Arm auto-merge on every open PR that is not a draft and not already armed (AUTHOR= limits it to one lane; DRY=1 calls nothing — issue #912)
	python3 scripts/arm_auto_merge.py arm $(if $(AUTHOR),--author "$(AUTHOR)",) $(if $(DRY),--dry,)

arm-auto-merge-report: ## Show the open PRs that carry no auto-merge intent yet, with their author and mergeable state (issue #912)
	python3 scripts/arm_auto_merge.py report $(if $(AUTHOR),--author "$(AUTHOR)",)
