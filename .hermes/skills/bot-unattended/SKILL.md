---
name: bot-unattended
description: The shared contract of every unattended llgenie bot leg — no user, never ask, and what to do when a decision is genuinely open. Preloaded alongside every bot skill.
---

# bot-unattended

Every llgenie bot leg runs detached: a CI job starts Hermes with `--yolo` and no user is
attached. This skill is the one place that contract lives; a bot skill names what its run
does, this one says how the run must end.

## Inputs

- Nothing of its own. It is preloaded with the bot's own skill (`hermes -s <bot>,bot-unattended`).

## Output

- No file. It shapes the output the bot's own skill defines.

## Rules

- **Never ask a question and never wait for input.** `--yolo` auto-approves shell commands
  and `--accept-hooks` auto-approves hooks, but neither answers Hermes's own `clarify` tool.
  In a detached run a `clarify` makes Hermes print `Input required; detached without
  cancelling`, exit 3, and leave the tree unchanged — the leg then reports "changed
  nothing", which is a misleading diagnosis of a run that died.
- **A question fails the run.** If a decision is genuinely open, take the path that needs
  none: the verdict the bot's own skill defines for "still open" (a refine with its
  `REFINED`/`REASON`, a close with cited `EVIDENCE`, a `DISTINCT`), or the safest
  reversible choice. State which path you took and why, in the output the skill defines.
- **Stay inside the run's writable set.** The bot's own skill names the files that leg may
  write; everything else in the repository is read-only for that run.
- **The rerun is the reader.** Nothing you print reaches a human directly; the file your
  skill defines is what the next step — and a reviewer — reads. Write it in the exact shape
  the skill requires, and do not add a second file of your own.
- **The repository's durable rules are `AGENTS.md`** (already in your context). Where this
  skill and `AGENTS.md` disagree about a repository-wide rule, `AGENTS.md` wins; where they
  disagree about what this leg may do, this skill wins, because it is the leg's contract.
