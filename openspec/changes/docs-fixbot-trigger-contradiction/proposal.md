# docs(bots): fix the stale fix-bot trigger description in BOTS.md

## Why

`docs/BOTS.md` disagrees with itself about the fix-bot's triggers. The manual-only
declaration at `docs/BOTS.md:62-66` (the change that made it manual-only, owner
directive 2026-11-08, #2293) says the bot wakes only on `workflow_dispatch`, while
`docs/BOTS.md:2613` still claims it runs on an "hourly `schedule` + `workflow_dispatch`".

The stale sentence teaches the pre-#2293 automation shape to a reader or bot-schedule
audit that lands there, and a re-added auto-trigger now fails `make check-workflows` —
so the sentence contradicts the very gate it is meant to warn about. Measured against
`.github/workflows/fix-bot.yml` (at `5cc544cf`), which has no `schedule` and no
`workflow_run`: `workflow_dispatch` with `pr_number`/`branch`/`check` inputs only.

## What changes

- Rewrite the `docs/BOTS.md:2613` sentence (the one opening the fix-bot make-target
  block) so it states the fix-bot is `workflow_dispatch`-only and **MANUAL-ONLY**,
  matching the authoritative text at lines 62-66. A person (or the run-failure-reactor,
  itself a human dispatch) hands it a PR or branch. No surviving sentence in the file
  describes an hourly auto-repair trigger the tree does not have.
- The surrounding make-target block describes sweep / resolve / report commands driven by
  a human; it implies no automation and is left as the (correct) manual recipe it is.
- Documentation record: an `agent-wiki/` note and a `docs/changes.d/` fragment indexed by
  `CHANGES.md`, both keyed to issue #2322.

## Who

architect lane (this is the paired docs half of the structural audit that also produced
the ARCHITECTURE.md fix in PR #2321).
