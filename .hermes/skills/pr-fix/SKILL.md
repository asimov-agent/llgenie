---
name: pr-fix
description: Repair a red CI run on an llgenie pull request from the failing check's output — fix the cause, never mock or weaken a gate, and commit nothing (the loop pushes only on green).
---

# pr-fix

The fix-bot loop (`scripts/fix_loop.sh`) runs a deterministic check, hands you its output, and
re-runs it. You repair the cause. The loop commits and pushes nothing; a workflow pushes the
working-tree change as one commit only when the loop ends green, and a human still reviews it.

## Inputs

- The prompt on STDIN: this skill's contract plus the failing check's last lines, the command
  that produced them, and — when the loop is repairing a *run's* captured log rather than a
  local check — that log.
- The report file (`$FIX_REPORT`) for more of the output than the prompt carries.
- `AGENTS.md` at the repo root — the repository's durable rules. Where this skill and
  `AGENTS.md` disagree, `AGENTS.md` wins.

## Output

- A fixed working tree. No commit, no push, no PR, no merge, no rebase, no `main`.

## Rules

- **The code is the default.** Find the defect the failing check points at and fix it.
- **A test may be updated only when the test itself is wrong** — it asserted the old
  behaviour, it hard-coded something that legitimately changed, or it exercises real logic the
  fix moved. Say why in the commit message the workflow writes.
- **Never** mock or stub the system under test, skip / `xfail` / delete an assertion, weaken a
  check, or silence a gate to make it pass. *Business logic is never mocked*, and a missing
  prerequisite is a loud failure, never a skip. A red check you cannot fix honestly is a
  result: leave the tree as it was and let the loop report it.
- **Verify your own work**: run the failing command again (the loop does this for you) and the
  gates around it — `make lint`, `make check-wiring`, `make openspec-validate NAME=<change>`,
  and the test files you touched. A new test file or make target must be wired, or
  `make check-wiring` fails by design.
- **Do not edit `.github/workflows/**` to change the outcome**, and do not create or modify
  credentials. Tokens arrive from CI secrets at run time.
- **Do not commit, push, merge, rebase, or touch `main`.** The workflow pushes your
  working-tree changes as one commit only if the loop ends green.
