---
name: rebase-conflict
description: Use when an llgenie rebase-bot run has stopped on a git conflict and the agent must resolve it, stage the files, and leave the rebase to the caller.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, rebase-bot, conflict]
---

# Rebase conflict resolution

The host rebased a pull request's branch onto `main`, hit a conflict, and stopped. The prompt you
received names the conflicted files. Resolve them; the caller continues the rebase.

## Inputs

- The conflict prompt on STDIN: the conflicted file list and what each side means.
- `HEAD` is `main` — it may carry a sibling PR that touched the same lines.
- The replayed commit is the PR's own work.
- The files themselves: read both sides in the working tree before choosing.

## Output

- The conflicted files **resolved and staged** (`git add`), with no conflict markers anywhere.
- Then stop. `git rebase --continue` is the caller's step, and so is the push.

## Rules

- **Preserve BOTH sides' intent.** A token-level union that drops one side's change is wrong even
  when it compiles and the suite passes.
- **Never weaken, delete or xfail a test to make the rebase apply.** If the two sides genuinely
  contradict each other, say so in your final message and leave the tree as it was.
- **Keep a Makefile recipe's leading TAB.** `make -n ci-unit` must still parse — a conflict in the
  `Makefile` is common, and a space-indented recipe is a broken tree.
- **Do not rewrite the PR's history beyond resolving this conflict**: no extra commits, no revert, no
  squash.
- **Leave no `<<<<<<<` / `>>>>>>>` marker in any file.** The host greps for them and refuses to push
  if one survives — including in a file it did not list.
