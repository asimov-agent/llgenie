# Tasks

- [x] Extend `scripts/check_pr_closing.py` so a claimed issue is an adjacent close in the joined commit messages and, when the body is supplied, in the pull request body.
- [x] Lock that behaviour in `tests/test_check_pr_closing.py`, including a real git range.
- [x] Pass the body file, `PR_BASE`, `PR_BRANCH` and `PR_TITLE` from the unit job, the guard step and the scope step. Keep the gate deferred and update the reason.
- [x] State the rule under the existing AGENTS.md heading, and record it in `docs/BOTS.md`, `agent-wiki/` and `docs/changes.d/`.
- [x] `make openspec-validate NAME=closes-in-squash-and-body` passes and the closing-keyword tests pass.
