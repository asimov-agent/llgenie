# mk/agents.mk — the fleet/agent plumbing domain (issue #2676)
# Moved byte-identically from the top Makefile: pure move, recipes and ## help lines
# unchanged; .PHONY lines, variables and banners stay at the top (domain files declare
# zero variables). The 30 targets are the roster from the issue; `agent-image-ref` is
# excluded by recipe (it is an image ref: scripts/ci_images.py latest agent) and rides
# mk/images.mk with the sibling images-domain issue.

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

provision-agent-profiles: ## Materialise EVERY lane's agents/<profile>/ into its Hermes home recursively, idempotently, land the model chain into every lane profile's config.yaml, then gate the result back against the tree (issue #2165, chain #2929) — the profile-creation/rebuild entrypoint (DEST=; CHECK=1 compares instead of writing; ROOT=; RESOLVE=1 additionally proves each lane's skills resolve through `hermes -p <lane> skills list`, issue #2669) — HOST-ONLY: a CI runner has no live profiles to provision, but the caller wires it into install so a rebuild cannot skip it
	@$(PY) scripts/provision_agent_profiles.py $(if $(DEST),--dest "$(DEST)",) $(if $(CHECK),--check,) $(if $(ROOT),--root "$(ROOT)",) $(if $(RESOLVE),--resolve,)

apply-hermes-base-config: ## Merge the model chain from agents/hermes-base-config.yaml into every llgenie-* lane profile's config.yaml (--lanes: the interactive default home's own model config is NOT touched — the chain owns the bots, not the human's session; PROFILE_HOME= overrides the profiles parent) (CHECK=1 compares instead of writing) — HOST-ONLY: the image installs the chain through the SAME seam via install_hermes_ci.sh + provision_agent_profiles.py (issue #2929)
	@$(PY) scripts/apply_hermes_base_config.py --lanes $(if $(PROFILE_HOME),--profiles-parent "$(PROFILE_HOME)",) $(if $(CHECK),--check,)

seed-hermes-profile-env: ## Move this shell's NOUS_API_KEY into the .env files Hermes actually reads: `hermes -p <lane>` resolves model.key_env from the PROFILE's own .env, not the caller's environment (measured against Hermes 0.23.2, issue #2929) — HOST-ONLY: --lanes leaves the interactive default home's .env alone, and the agent image seeds every leg's profiles at leg start through its /etc/profile.d hook, so no CI runner needs this target. Never invents or prints a value (CHECK=1 verifies without writing; PROFILE_HOME= overrides the profiles parent)
	@$(PY) scripts/seed_profile_hermes_env.py --lanes $(if $(PROFILE_HOME),--profiles-parent "$(PROFILE_HOME)",) $(if $(CHECK),--check,)

skill-parity: ## Report live↔tree skill parity for every llgenie profile (issue #1924, Layer A) — HOST-ONLY and READ-ONLY: it diffs agents/<profile>/skills/ against the live ~/.hermes/profiles/<profile>/skills/ and prints live-only / tree-only counts and names; it NEVER writes (a CI runner has no live profiles, so this is one finding that needs a caller where they exist). No sync, no fold (#791/#1062)
	@python3 scripts/skill_parity.py report

tester-fold-live: ## Enumerate a described live host-agent lane's files against its tree copy; COPY=1 writes live→tree (PROFILE=<profile>; issue #1079) — host-only: a CI runner has no live profile to fold from
	@test -n "$(PROFILE)" || { echo "Usage: make tester-fold-live PROFILE=<profile> [COPY=1]"; exit 2; }
	python3 scripts/fold-live-profile.py --profile "$(PROFILE)" $(if $(COPY),--copy,)

profile-drift-alarm: ## The SCHEDULED caller for #928: run on a host with live profiles, file ONE issue on drift (exit 2 = could not compare, 3 = drift)
	@python3 scripts/profile_drift_alarm.py --file-issue

check-cron-drift: ## Fail when a live planner cron prompt (auto-approve-merge db0a3e1a3d7c, auto-rebase-resolve 71c5192ebdba) diverges from its versioned copy under agents/llgenie-planner/prompts/ (issue #2359) — host-only: a CI runner has no live jobs.json; exit 0 all identical, 1 any drift, 2 a read/missing failure (LIVE=; ROOT=), HOST-ONLY
	@python3 scripts/check_cron_drift.py $(if $(LIVE),--live "$(LIVE)",) $(if $(ROOT),--root "$(ROOT)",)

verify-lane-contract: ## Verify each live llgenie lane's SOUL commits to the behavioural contract (report line, never-merge, bookend, versioned-edit, own duty, communication + materialised skills) — host-only: a CI runner has no live ~/.hermes profiles; prints `N/13 lanes pass` and names FAIL lanes + the missing element (issue #2260)
	@python3 scripts/verify_lane_contract.py

profile-drift: ## Fail when a tree copy is a PREFIX of the live rulebook (issue #928) — host-only: a CI runner has no live profiles, so this is the one finding that needs a caller where they exist
	@python3 scripts/check_agent_profiles.py check --only live-longer

lane-preflight: ## Run the FAST gates before a host lane pushes, printing one line per gate and a final verdict; imports FAST_GATES from issue_bot_gates.py (one list) and refuses a dirty tree so the verdict describes the would-be-pushed head (issue #1058)
	python3 scripts/lane_preflight.py run

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
	leg_start=$$(date +%s); hermes -z "Follow the preloaded skill agent-fetch: the URL is $(URL) and the output file is $(OUT)." -s agent-fetch,bot-unattended -p llgenie-documentation-maintainer --reasoning $(HERMES_REASONING) --yolo; rc=$$?; python3 scripts/hermes_model_route.py --lane llgenie-documentation-maintainer --since $$leg_start; exit $$rc

search-smoke: ## Prove the masked web reach works: one real Firecrawl request with a hard budget, loud on 401/402/403 — never an empty result (BUDGET= chars, default 4000)
	@python3 scripts/require_env.py FIRECRAWL_API_KEY
	@python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo \
	  $(AGENT_SHELL_FORWARD_PLAIN) $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  -e BUDGET \
	  $(AGENT_IMAGE) bash -lc 'python3 scripts/fetch_smoke.py --budget "$${BUDGET:-4000}"')

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
	python3 scripts/hermes_smoke.py run --profile llgenie-status-keeper --reasoning low

agent-image-profiles-check: ## CI (publish-agent-image, post-publish): boot the agent image the lane just published (the standard agent leg: guard, scrubbed stream, forwarded keys, bot marker) and assert every profile declared in agents/manifest.json exists where Hermes resolves `-p <lane>` ($HERMES_HOME/profiles/<lane>/). Prints OK/MISSING per lane; any MISSING reddens the publish lane (issue #2934)
	@python3 scripts/require_env.py NOUS_API_KEY
	python3 scripts/ci_images.py ensure agent
	$(call scrubbed_run,$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo -e NOUS_API_KEY \
	  -e TYPESAFE_API_KEY -e HERMES_NERVE_PROVIDER -e NERVE_REQUIRE \
	  $(AGENT_SHELL_FORWARD) $(AGENT_BOT_MARKER) \
	  $(AGENT_IMAGE) bash -lc 'make _agent-image-profiles-check')

_agent-image-profiles-check: # (internal) runs INSIDE the agent image: assert every agents/manifest.json
# lane has its profile config at $HERMES_HOME/profiles/<lane>/config.yaml — the exact path Hermes
# resolves `-p <lane>` from (issue #2934).
	@python3 scripts/agent_image_profiles_check.py --manifest agents/manifest.json

nerve-profile-check: ## Probe the rule the agent image build enforces: a nerve setting whose module the selected profile does not register is inert, so the build fails (issue #611)
	python3 scripts/nerve_profile_check.py --self-test

memory-install:
	@[ "$${DRY_RUN:-0}" = "1" ] && python3 scripts/memory_bootstrap.py install --dry-run || python3 scripts/memory_bootstrap.py install

memory-bootstrap:
	python3 scripts/memory_bootstrap.py bootstrap $${PROFILE:+--profiles $$PROFILE} $${DRY_RUN:+--dry-run}

memory-verify:
	python3 scripts/memory_bootstrap.py verify $${PROFILE:+--profiles $$PROFILE}

memory-check:
	python3 scripts/memory_bootstrap.py check $${PROFILE:+--profiles $$PROFILE} $${PORT:+--port $$PORT}

memory-render:
	python3 scripts/memory_bootstrap.py render $${PROFILE:+--profiles $$PROFILE} $${DRY_RUN:+--dry-run}

memory-status:
	python3 scripts/memory_bootstrap.py status $${PROFILE:+--profiles $$PROFILE} $${PORT:+--port $$PORT}

bind-proof: ## Bind a proof run's head_sha to the PR head it is cited for — fail unless the run proved the CURRENT head (PR= RUN=, issue #1293)
	@test -n "$(PR)" && test -n "$(RUN)" || { echo "Usage: make bind-proof PR=<n> RUN=<run-id>"; exit 1; }
	python3 scripts/bind_proof.py --pr $(PR) --run $(RUN)

check-main-ruleset: ## CI: fail when the main ruleset has no required_status_checks or misses a pinned context (the missing merge-block gate, issue #1400) — runs in the monitor workflow main-ruleset.yml; exits 2 when the ruleset cannot be read
	python3 scripts/check_main_ruleset.py check --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),)

main-ruleset-report: ## Print the main ruleset's measured state and the pinned required contexts, always exit 0 (issue #1400)
	python3 scripts/check_main_ruleset.py report --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),)

main-ruleset-apply: ## DRY by default: print the add-only required_status_checks PUT body; APPLY=1 with an admin token performs it (owner-admin-only, issue #1400)
	python3 scripts/check_main_ruleset.py apply --repo $(GH_REPO) $(if $(RULESET_ID),--ruleset-id $(RULESET_ID),) $(if $(filter 1,$(APPLY)),--apply,)
