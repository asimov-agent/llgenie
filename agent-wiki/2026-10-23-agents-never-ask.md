# 2026-10-23 — unattended agents never ask (#543)

**Issue:** [#543](https://github.com/asimov-agent/llgenie/issues/543) · **PR:** the PR that closes it

## What was wrong

`hermes -z … --yolo` auto-approves shell commands and `--accept-hooks` auto-approves hooks; neither answers the
agent's `clarify` tool. A question in a detached run detaches Hermes with exit **3**, leaves the tree unchanged,
and the leg reports "changed nothing" — so the reader chases data, keys or an alias. Measured in the sibling
repo's issue-bot (run `39905705714`, job 120257209801):

```
[agent] Input required; detached without cancelling. Resume this session interactively.
[agent] make: *** [Makefile:1001: _implement-issue] Error 3
##[error]issue-bot produced no implementation for #202 (make implement-issue rc=2).
```

llgenie had the same exposure: five agent prompts, none of which said the run has no user.

## What changed

- The UNATTENDED rule on all five `hermes -z` prompts (triage, implement, refiner, architecture, fetch):
  never ask, never wait; a genuinely open decision becomes a `refine` with `REASON` (or the safest reversible
  choice, stated in the output) because "a question fails the run".
- `scripts/fix_bot_rules.md`: a "You are unattended" section with the same contract for the repair loop.
- `issue-bot.yml`: the failure step reports `rc == 3` as "the agent asked for input (Hermes detached)", before
  the generic "changed nothing" message.
- `tests/test_agents_unattended.py` reads the real Makefile, rules file and workflow.

## Verified

- `pytest tests/test_agents_unattended.py` in `llgenie/test:latest` → 3 passed.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=agents-never-ask`, `make openspec-tasks-check` → green.
- `make test-unit` runs in the PR's checks.
