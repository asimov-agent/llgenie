# "Implemented" is measured from the tree, not from the exit code

- Issue: [#428](https://github.com/asimov-agent/llgenie/issues/428)
- OpenSpec change: `bot-changed-from-tree`
- Branch: `fix/bot-changed-from-tree`

## What was wrong

`issue-bot.yml` set `implemented=true` whenever `make implement-issue` exited 0, and gated the
"fail loudly when the implementation did not happen" step on `implemented != 'true'` — so the one check
written for a no-op could never fire on one. Run 39513850754 exited 0 having "committed" `ad266c6`
inside a container worktree that `--rm` deleted; the step reported `skipped`, and the run shipped PR
#424 as an implementation of #407.

## What changed

- `scripts/issue_implementer.py` — `changed()` reads `git status --porcelain --untracked-files=all` and
  ignores the bot's own run inputs (`issue.md`, `triage.md`, `refine-in.md`, `refine.md`, `comment.md`);
  the `changed` subcommand prints `changed=true|false`, and a `git` that cannot read the tree exits 2.
- `Makefile` — `make issue-bot-changed` (`.PHONY`, `##` help line), so the workflow runs a target, not
  a bare `git`.
- `.github/workflows/issue-bot.yml` — a `Detect what the implementation changed` step; the push requires
  `changed == 'true'`; the loud failure fires on `rc != 0` **or** `changed != 'true'`; `implemented` is
  gone, and the outcome comment reports `changed=` and the agent's `rc` separately.
- `tests/test_issue_implementer.py` — four real-git cases (no change, a real edit, an unreadable tree,
  and the workflow gating) added to the dispatcher suite.
- `README.md` — the target and what it measures.

## Verified

- `pytest tests/test_issue_implementer.py` → 33 passed (29 before, +4).
- `make issue-bot-changed` on the committed branch: `changed=false` with only `triage.md` written, and
  `changed=true` once a tracked file is edited (see the PR for the transcript).
- Exit-code contract: `issue_implementer.py changed --root <a plain directory>` → exit 2, stderr naming
  `status failed`.
- `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`,
  `make openspec-validate NAME=bot-changed-from-tree` — green.

## Notes

- The run-input filter lives in the script, so this change is correct on its own; with #427 landed the
  filter is redundant rather than wrong.
- Excluding run inputs here is not a denylist substitution: the *outcome* is now read from the tree,
  which is what #427's ignore file also serves. The two fixes are complementary, and both are linked
  from each PR's `Not covered`.
