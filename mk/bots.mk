# ---- issue-bot: one issue per run, at most 3/day (issue #248) -----------------
# The dispatcher is deterministic (no LLM): cap -> pick ONE -> claim -> issue.md
# + branch. `implement-issue` is the shared Hermes agent step (AGENTS.md is the
# authority the agent reads; #238 wires the token/plugin into the agent image).
# ---- rebase-bot: keep the open PRs on `main` (issue #246). ONE PR per 6-hourly run; a conflict
# is handed to the agent; the result is verified structurally and pushed with --force-with-lease
# to the PR's OWN head remote (a fork PR goes to the fork). It never merges.
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
bot-preflight: ## Fetch origin/main, fast-forward a behind checkout, and record the AGENTS.md this run is measured against (issue #792); when the working diff touches agents/<profile>/, surfaces the #1724 SYNC-line obligation (BODY=<prospective PR body> refuses a missing/mis-cited SYNC line, issue #1782)
	python3 scripts/bot_preflight.py $(if $(CHECK),--check,) $(if $(BODY),--body-file "$(BODY)",)
bot-stamp-body: ## Stamp BODY=<pr body file> in place (or into OUT=) with the `AGENTS:`/`BASE:` pair measured at origin/main — the ONE stamp authority every bot PR producer calls before `gh pr create`/`gh pr edit`, so a bot PR never opens unstamped (issue #2050); BASE=/REFS= name the main ref a producer's checkout actually stands on
	@test -n "$(BODY)" || { echo "Usage: make bot-stamp-body BODY=<pr body file> [OUT=<file>] [BASE=origin/main] [REFS=origin/HEAD,main]"; exit 1; }
	python3 scripts/bot_preflight.py --stamp "$(BODY)" $(if $(OUT),--out "$(OUT)",) $(if $(BASE),--base "$(BASE)",) $(if $(REFS),--refs "$(REFS)",)
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
skill-parity: ## Report live↔tree skill parity for every llgenie profile (issue #1924, Layer A) — HOST-ONLY and READ-ONLY: it diffs agents/<profile>/skills/ against the live ~/.hermes/profiles/<profile>/skills/ and prints live-only / tree-only counts and names; it NEVER writes (a CI runner has no live profiles, so this is one finding that needs a caller where they exist). No sync, no fold (#791/#1062)
	@python3 scripts/skill_parity.py report
tester-fold-live: ## Enumerate a described live host-agent lane's files against its tree copy; COPY=1 writes live→tree (PROFILE=<profile>; issue #1079) — host-only: a CI runner has no live profile to fold from
	@test -n "$(PROFILE)" || { echo "Usage: make tester-fold-live PROFILE=<profile> [COPY=1]"; exit 2; }
	python3 scripts/fold-live-profile.py --profile "$(PROFILE)" $(if $(COPY),--copy,)
profile-drift-alarm: ## The SCHEDULED caller for #928: run on a host with live profiles, file ONE issue on drift (exit 2 = could not compare, 3 = drift)
	@python3 scripts/profile_drift_alarm.py --file-issue
check-tick-prompt: ## Fail when the live orchestrator cron prompt diverges from the versioned copy under agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md (issue #2159) — host-only: a CI runner has no live jobs.json; exit 0 identical, 1 diverged, 2 a read/missing failure (LIVE=; VERSIONED=), HOST-ONLY
	@python3 scripts/check_tick_prompt.py $(if $(LIVE),--live "$(LIVE)",) $(if $(VERSIONED),--versioned "$(VERSIONED)",)
verify-lane-contract: ## Verify each live llgenie lane's SOUL commits to the behavioural contract (report line, never-merge, bookend, versioned-edit, own duty, communication + materialised skills) — host-only: a CI runner has no live ~/.hermes profiles; prints `N/13 lanes pass` and names FAIL lanes + the missing element (issue #2260)
	@python3 scripts/verify_lane_contract.py
check-cron-drift: ## Fail when a live planner cron prompt (auto-approve-merge db0a3e1a3d7c, auto-rebase-resolve 71c5192ebdba) diverges from its versioned copy under agents/llgenie-planner/prompts/ (issue #2359) — host-only: a CI runner has no live jobs.json; exit 0 all identical, 1 any drift, 2 a read/missing failure (LIVE=; ROOT=), HOST-ONLY
	@python3 scripts/check_cron_drift.py $(if $(LIVE),--live "$(LIVE)",) $(if $(ROOT),--root "$(ROOT)",)
profile-drift: ## Fail when a tree copy is a PREFIX of the live rulebook (issue #928) — host-only: a CI runner has no live profiles, so this is the one finding that needs a caller where they exist
	@python3 scripts/check_agent_profiles.py check --only live-longer
# ---- a leg refuses to start on a missing key (issue #363) --------------------
# A leg that forwards a key its job never set spends the runner first: it pulls the image,
# starts a container, and fails inside Hermes — a 120-180 minute-timeout job lost to a
# plumbing mistake, and a log that reads like a model problem. The guard runs BEFORE
# `ci_images.py ensure agent`, prints the NAME only, and exits 2 (never a skip). The key list
# per leg is the one that leg actually forwards; the suite derives the roster from this file,
# so a new leg without a guard fails the test.
require-env: ## Refuse to start when a credential a leg needs is missing (KEYS="NOUS_API_KEY ..."; name-only, exit 2)
	@test -n "$(KEYS)" || { echo "Usage: make require-env KEYS=\"NOUS_API_KEY [TYPESAFE_API_KEY]\""; exit 1; }
	python3 scripts/require_env.py $(KEYS)
# `$(call …)` splits its arguments on COMMAS IN THE UNEXPANDED TEXT, so a literal `-s a,b` inside
# the call keeps only `-s a`: the rest is dropped, the shell sees an unclosed quote, and the leg dies
# with `unexpected EOF while looking for matching '` before the agent starts (issue #641, measured on
# #602/#605 staying DIRTY). The skills therefore come from a variable — no comma in the call text —
# and `make -n rebase-bot-agent` is the proof.
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
scrub-log: ## Redact a captured agent log and print its bounded tail (LOG=<path>, OUT=<redacted path>, TAIL=<lines>) — the same redactor every agent leg runs (issue #359)
	@test -n "$(LOG)" || { echo "Usage: make scrub-log LOG=<captured log> [OUT=<redacted path>] [TAIL=60]"; exit 1; }
	python3 scripts/scrub_log.py --in "$(LOG)" $(if $(OUT),--out "$(OUT)",) --tail $(if $(TAIL),$(TAIL),$(HERMES_LOG_TAIL))
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
worktree-prune: ## Remove the worktrees and local branches whose PR already merged, proven by the PR's merge commit (squash merges defeat ancestry, issue #431); DRY=1 prints the plan, BASE= picks the base ref, SLUG= the owner/name gh reads; an UNATTENDED run — CI, BOT, or the dispatcher's HERMES_KANBAN_* — is REFUSED unless CONFIRM=1 (issue #794)
	@python3 scripts/worktree_prune_guard.py
	python3 scripts/worktree_prune.py --repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie) --base $(if $(BASE),$(BASE),origin/main) $(if $(DRY),--dry,)
queued-alarm: ## Report jobs stuck in `queued` far too long (a runner that never picks them up, issue #254); COMMENT=1 delivers the report, DRY=1 previews it
	python3 scripts/queued_run_alarm.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(COMMENT),--comment,) $(if $(DRY),--dry,)
check-zero-job-pending: ## Fail when a dispatched run has been pending/queued longer than MINUTES with ZERO jobs instantiated (none named it: queued-alarm scans job rows, reactor needs a conclusion; issue #1410); FILE=1 files ONE deduped issue per stuck run
	python3 scripts/check_zero_job_pending.py --repo $(GH_REPO) --minutes $(if $(MINUTES),$(MINUTES),30) $(if $(filter 1,$(FILE)),--file,)
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
arm-auto-merge: ## Arm auto-merge on every open PR that is not a draft and not already armed (AUTHOR= limits it to one lane; DRY=1 calls nothing — issue #912)
	python3 scripts/arm_auto_merge.py arm $(if $(AUTHOR),--author "$(AUTHOR)",) $(if $(DRY),--dry,)
arm-auto-merge-report: ## Show the open PRs that carry no auto-merge intent yet, with their author and mergeable state (issue #912)
	python3 scripts/arm_auto_merge.py report $(if $(AUTHOR),--author "$(AUTHOR)",)
