# The bots' run inputs are ignored by construction, not by a denylist

- Issue: [#427](https://github.com/asimov-agent/llgenie/issues/427)
- OpenSpec change: `bot-scratch-ignored`
- Branch: `fix/bot-scratch-ignored`

## What was wrong

`triage.md` was the one run input missing from `.gitignore`, so the push step's `git add -A` committed
it on any run whose implementation changed nothing, and the workflow answered the gap with a
`git reset -q -- issue.md` denylist that named a different file. Run 39513850754 thus shipped
`TRIAGE: implement` as the implementation of #407 (PR #424) with `closes #407` on it.

## What changed

- `.gitignore` — `triage.md` joins `issue.md`, `refine-in.md`, `refine.md`, `comment.md`; the comment
  says which leg writes which, that the list is the whole set, and that a workflow must not answer a gap
  with `git reset -- <file>`.
- `.github/workflows/issue-bot.yml` — the `git reset -q -- issue.md` line is gone; `git add -A` plus the
  ignore file is the one rule.
- `tests/test_bot_scratch_ignored.py` — real-git checks in both directions: every roster name is
  ignored (`git check-ignore`), the `.gitignore` run-input block and the roster are the same set, every
  roster name is written by a producer, the push step carries no per-file exclude, and in a throwaway
  repo holding this `.gitignore` a written `triage.md` is not a pending change while a real file is.
- `README.md` — the run-input contract, next to the triage/verdict flow.

## Verified

- `git check-ignore -v triage.md` → `.gitignore:59:triage.md` (and the other four, same answer).
- `pytest tests/test_bot_scratch_ignored.py` → 4 passed.
- `make test-unit`, `make lint`, `make check-docs`, `make check-workflows`,
  `make openspec-validate NAME=bot-scratch-ignored` — green (numbers in the PR).

## Notes

- The ignore file alone is not the whole fix for the "no implementation" class: the exit code is still
  read as "implemented" (#428) and the agent still works in place vs. a worktree (#426). Both are filed
  and linked from the PR.
- `comment.md` was already ignored, so the roster check is the thing that keeps the set complete — the
  test fails on a name added to `.gitignore` without the roster, and on a roster entry nobody writes.
