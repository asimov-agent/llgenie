---
name: pr-fix
description: Use when the llgenie fix-bot is repairing a red CI run on a pull request — find the defect, change it honestly, verify with the repo's gates, never push.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, fix-bot, repair]
---

# PR repair

You are repairing a **red CI run on an llgenie pull request**. `AGENTS.md` governs the repository;
where anything below and the repository disagree, `AGENTS.md` wins.

## Inputs

- The prompt: the failing check's command and the last lines of its report.
- `$FIX_REPORT`: the whole report, when the tail is not enough.
- The tree itself: the failing test or script names the code path. Read it before editing.

## Output

- **The repair, in the working tree, uncommitted.** The loop pushes your changes as one commit
  *only* if the check ends green; a human reviews the result.

## Rules

- **The code is the default.** Find the defect the failing check points at and fix the cause, not
  the symptom.
- **A test may be updated only when the test itself is wrong** — it asserted the old behaviour, it
  hard-coded something that legitimately changed, or it exercises logic the fix moved. Say why in
  the commit's body.
- **Never** mock or stub the system under test, skip/`xfail`/delete an assertion, weaken a check, or
  silence a gate to make it pass. A red check you cannot fix honestly is a result: leave the tree as
  it was and let the loop report it.
- **Verify before you finish**: the failing command again, plus `make lint`, `make check-wiring`,
  `make openspec-validate NAME=<change>`, and the tests you touched. Everything goes through the
  Makefile — CI runs the same commands, and a new test file or target must be wired or
  `make check-wiring` fails (by design).
- **Do not commit, push, merge, rebase or touch `main`.** Do not edit `.github/workflows/**` to
  change the outcome, and never create or modify credentials — tokens arrive from CI secrets at run
  time.
- **Say what you changed and why**, in your final message: the loop's report quotes it, and a
  reviewer reads it instead of re-deriving your reasoning.
