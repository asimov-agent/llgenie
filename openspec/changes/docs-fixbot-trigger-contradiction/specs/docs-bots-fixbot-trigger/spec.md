# docs-bots fixbot trigger contradiction

## MODIFIED Requirements

### Requirement: BOTS.md names only the real fix-bot triggers (workflow_dispatch, manual-only)

`docs/BOTS.md` MUST describe the fix-bot's trigger surface the way the tree actually
defines it and the manual-only owner directive (2026-11-08, #2293) enacted it. Every
fix-bot trigger description in the file MUST say `workflow_dispatch` only — by a person,
or by the run-failure-reactor, itself a human dispatch. No sentence MAY claim an hourly
`schedule`, a `workflow_run`, or any other auto-trigger for the current fix-bot. A
historical reference (e.g. "used to be woken… on `workflow_run` and its own hourly
`schedule`. Both auto-triggers are gone") is a negation that names the SHAPE that was
removed, not a current trigger, and is allowed — it matches the authoritative section.

WHEN a reader or an automation-facing docs check greps `docs/BOTS.md` for a fix-bot
trigger, THEN the trigger descriptions it finds all say the bot starts only on
`workflow_dispatch` (manual, or a human dispatch) — with no statement that the bot
currently wakes hourly or on any auto-trigger.

#### Scenario: the fix-bot make-target block no longer claims an hourly schedule

- **Given** the fix-bot make-target block in `docs/BOTS.md` (the `make fix-bot-*` block, formerly around line 2613)
- **When** the block describes how the bot is triggered
- **Then** it says `workflow_dispatch`-only / manual-only and never says "hourly `schedule` + `workflow_dispatch`" or an equivalent for the current bot
- **Test:** `grep -n "fix-bot\.md.*schedule\|fix-bot.?\?.*hourly" docs/BOTS.md` returns nothing that describes a CURRENT fix-bot hourly schedule (the only remaining hits are the explicit historical negations in the manual-only section and the `:17 slot is gone` line)

#### Scenario: the fix-bot trigger descriptions match the manual-only source of truth

- **Given** the authoritative manual-only declaration at `docs/BOTS.md:62-66` (owner directive 2026-11-08, #2293)
- **When** any other fix-bot trigger mention is read
- **Then** it agrees: the bot is manual-only, starts on `workflow_dispatch`, and a re-added auto-trigger fails `make check-workflows`
- **Test:** the rewritten `docs/BOTS.md` fix-bot text and the workflow's own `on:` block (`.github/workflows/fix-bot.yml` — `workflow_dispatch` only) both state the same triggers
