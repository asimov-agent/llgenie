---
name: rebase-conflict
description: Resolve one stopped git rebase conflict on a PR branch onto main, preserving both sides' intent, staging the files and stopping — the caller continues the rebase.
---

# rebase-conflict

`scripts/rebase_bot.sh` rebased one PR branch onto `origin/main`; the rebase stopped on a
conflict and its prompt — the conflicted files and what each side means — arrives on STDIN.

## Inputs

- STDIN: the conflict prompt. It names the conflicted files (`git diff --name-only
  --diff-filter=U`) and states what each side is: `HEAD` is `main` (possibly a sibling PR that
  touched the same lines); the replayed commit is the PR's own work.
- The working tree, mid-rebase. Read the files and the replayed commit
  (`git log --oneline origin/main..HEAD`, `git show`).

## Output

- The conflicted files resolved and staged (`git add`), then stop. The caller runs
  `git rebase --continue`; do not run it yourself.

## Rules

- **Preserve BOTH sides' intent.** A token-level union that drops one side is wrong; so is
  taking `ours`/`theirs` wholesale.
- **Never weaken, delete or xfail a test** to make the rebase apply, and never silence a gate.
  A test that truly needs a change is a change to explain, not to delete.
- **Keep a Makefile recipe's leading TAB** — `make -n ci-unit` must still parse.
- Do not rewrite the PR's history beyond resolving this conflict, do not push, do not merge.
- **Leave no conflict markers anywhere** (`<<<<<<<`, `=======`, `>>>>>>>`); the caller greps for
  them and stops the run if any remain.
