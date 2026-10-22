# A bot PR opened with the job token has no checks at all

- Issue: [#497](https://github.com/asimov-agent/llgenie/issues/497)
- Augments: the fork-head work in #488/#489 and the `workflow_run` merge in #492/#493
- OpenSpec change: `bot-pr-token-triggers-ci`
- Branch: `fix/bot-pr-token-triggers-ci`

## What was wrong

`gh pr checks 495` → `no checks reported on the 'agent/architecture-20261021T1814' branch`. Not "checks
failing", not "pending" — **no run existed**. The architecture bot opened its PR with `GH_TOKEN: ${{
github.token }}` (chosen for the issue write, since `secrets.BUMP_TOKEN` carries no Issues write, #412), and
GitHub starts **no workflows** for a pull request created with `GITHUB_TOKEN`. So nothing could ever be green,
every merge gate deferred on `BLOCKED`, and the bot then blocked itself: `open_architecture_pr()` refuses to
publish while an architecture PR is open.

## What changed

- `scripts/architecture_bot.py::_gh(gh, *args, token=…)` runs `gh` with its own `GH_TOKEN`, per call.
- `publish(..., pr_token=…)`: the issue keeps the job token, `gh pr create` uses `PR_TOKEN`; an empty value
  falls back to the inherited token (a local run) and prints a warning about the missing CI.
- `.github/workflows/architecture-bot.yml` publish step: `GH_TOKEN: ${{ github.token }}` **and**
  `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}`, with the reason in a comment.
- `tests/test_architecture_bot.py`: the recorded `gh` now records the token, so the test asserts the issue
  call carries the job token and the PR call carries the owner PAT; a second test reads the workflow.

## Verified

- `pytest tests/test_architecture_bot.py` → 13 passed.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-dispatch-forms`,
  `make openspec-validate NAME=bot-pr-token-triggers-ci` — green.
- `make test-unit` — green (numbers in the PR).

## Notes

- Audited the other producers: `engine-bump.yml` and `registry-sync.yml` already open their PRs with
  `secrets.BUMP_TOKEN`; `issue-bot.yml` was split in #430/#447. This was the last one.
- #495 stays un-mergeable (it has no run and cannot get one retroactively); the bot's next run publishes a
  fresh PR once it is closed.
