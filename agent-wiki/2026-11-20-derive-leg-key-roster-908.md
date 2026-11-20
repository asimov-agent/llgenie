# 2026-11-20 — The leg-key rule is derived from the tree, not a hand-kept roster (issue #908)

Implements issue #908 (OpenSpec change `derive-leg-key-roster`): the #364 rule ("the job that
calls a leg forwards the keys it needs") was enforced by two hand-kept rosters in
`tests/test_agent_shell_keys.py` (`BOT_JOBS` + `entries`) that named only 4 bot jobs; every
leg call outside them was unwatched. The roster is now derived at test time from the tree.

## What was verified against the spec

- **Derived walk** (`tests/test_agent_shell_keys.py`): `_target_bodies()` parses every
  target's recipe from `makefiles_text()` (include-resolved Makefile); `_make_calls()` names
  `make`/`$(MAKE)` invocations whose target token is a KNOWN target, so
  variable-assignment arguments (`make rebase-bot REPO=...`) are caught while prose cannot
  masquerade as a call — mentions after a `#` on the line and backtick-wrapped prose
  (docstrings/usage text, e.g. the `make auto-jev-preflight-explain` strings in
  `scripts/auto_merge.py`) are skipped; `_legs_run_by()` follows the recipe's make edges AND
  the shell scripts the recipe executes; `_leg_calls()` walks every `*.yml` job/step.
- **Measured board (this branch base `4f3fc1ef2`)**: 16 agent legs (recipes carrying
  `$(AGENT_IMAGE)`), 28 leg calls across 10 workflows
  (`architecture-bot, engine-bump, fix-bot, issue-bot, issue-dedupe, issue-refiner,
  publish-agent-image, rebase-bot, registry-sync-review, search-smoke`) — vs the old roster's
  4 pinned jobs; findings on main after the workflow fix: zero.
- **Wrapper shapes proven**: the recipe-nested wrapper (`$(MAKE) <leg>`) via the planted
  `sweep` fixture; the SCRIPT hop via the real rebase-bot case — the job runs
  `make rebase-bot`, whose recipe runs `scripts/rebase_bot.sh`, whose `AGENT_CMD` default
  `make -f $MK_SNAPSHOT rebase-bot-agent` is the leg call. Only `.sh` scripts are followed:
  a `make X` inside a `.py` string can be a validator regex (`check_workflows.py`'s
  `re.compile(r"make\s+agent-jev-preflight\b")`) or docs prose, not a call — following .py
  invents edges (measured false chain ci-unit → ci_unit.py → check-workflows →
  check_workflows.py → agent-jev-preflight).
- **Never vacuous**: the walk fails if it finds zero leg calls, and floors at ≥10 calls /
  ≥5 key assertions (base measured 28); the four calls the old `entries` pinned (fix-bot,
  issue-bot, issue-refiner, rebase-bot wrapper) are asserted as DERIVED members — the test
  reddens if the walk loses one.
- **Planted #364 shape end-to-end**: synthetic Makefile + workflow where a job calls a leg
  forwarding `-e GH_TOKEN` but sets it only in a SIBLING step's env — the walk reports the
  finding naming workflow/job/leg/key, names only the missing key (NOUS_API_KEY stays clean),
  and goes green when the job env sets it.
- **The real gap fixed**: `publish-agent-image.yml` — the `agent-image-profiles-check` and
  `hermes-smoke` steps run legs that forward `-e TYPESAFE_API_KEY` while the job set no
  TYPESAFE_API_KEY; both steps now carry `TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}`.
  This call site was invisible to the old 4-entry roster.
- `entries` is gone; `BOT_JOBS` stays hand-named only for the `agent-shell-keys-check`
  proof (a claim about what the job PROVES, not what a leg forwards), per its comment.

## Key decisions

- Token-scanning against KNOWN target names instead of a `make <target>` regex: assignments,
  quoted values, and flags can't hide a target, and unknown words (step-name prose like
  "a head", option values) can't invent one.
- Script hops restricted to shell scripts (see above); the restriction is stated in the
  helper's docstring so a future .py hop is a deliberate change, not an accident.

## Current status

Issue #908. All 10 tests in `tests/test_agent_shell_keys.py` green locally; full unit
battery + lane-preflight recorded on the PR.
