# Unattended agents never ask

## Why

`hermes -z … --yolo` auto-approves **shell commands**, and `--accept-hooks` auto-approves **hooks**. Neither
answers the agent's own `clarify` tool. In a detached run Hermes prints `Input required; detached without
cancelling. Resume this session interactively.` and exits **3**, the tree is unchanged, and the leg reports
"produced no implementation" / "changed nothing" — a diagnosis that points at data, keys or an alias and is
none of them. Measured in the sibling repo's issue-bot, run `39905705714` job 120257209801:

```
[agent] Input required; detached without cancelling. Resume this session interactively.
[agent] make: *** [Makefile:1001: _implement-issue] Error 3
##[error]issue-bot produced no implementation for #202 (make implement-issue rc=2).
```

llgenie's prompts describe verdicts, gates, OpenSpec and findings in detail, and said nothing about being
unattended, so any of its five agent legs could hit the same wall.

## What Changes

- **The rule is in every unattended prompt**: `_issue-bot-triage`, `_implement-issue`, `_issue-refiner`,
  `_architecture-bot-doc`, `_agent-fetch` each end with "UNATTENDED: this run has no user — NEVER ask a question
  and never wait for input … a question fails the run", and `scripts/fix_bot_rules.md` gains a
  "You are unattended" section with the same contract.
- **Exit 3 is named for what it is** in `issue-bot.yml`'s "Fail loudly when the implementation did not happen"
  step: `the agent asked for input (Hermes detached, rc=3)`, before the generic "changed nothing" message.
- **A test locks it**: `tests/test_agents_unattended.py` reads the real Makefile, rules file and workflow.

## Impact

- A resolvable issue is implemented instead of failing on a question nobody can answer, and when an agent does
  ask, the run says so.
- No behaviour change to the verdicts themselves; a refine still names its open decision in `REASON`.
