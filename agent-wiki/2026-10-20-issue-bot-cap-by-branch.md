# The issue-bot's 3-per-day cap counts its own PRs

Issue #409. OpenSpec change: `issue-bot-cap-by-branch`. PR: (this branch, opened against `asimov-agent/llgenie:main`).

## What was wrong

`scripts/issue_implementer.py::count()` — the cap numerator — searched
`gh search prs --author github-actions[bot]`. The issue-bot never opens a PR as that login: `issue-bot-open-pr`
runs `gh` with the owner PAT, so its PRs are authored `asimov-agent`. The cap read 0 whatever the bot did, so
the "hard bound" in `issue-bot.yml`'s own header was never enforced.

Measured 2026-10-20: `gh search prs --author 'github-actions[bot]'` → `[]`; the bot-opened PRs of 2026-10-19 are
authored `asimov-agent`. Those seven were engine-bump PRs — which must NOT count toward this cap — so the fix
cannot simply count the PAT owner either. The dispatcher's own branch shape is the signal.

## What changed

- `scripts/issue_implementer.py` — `count()` lists the repository's PRs (`gh pr list --json
  headRefName,author,createdAt`) and counts one when it was created today AND its head branch starts with
  `agent/issue-` (or its author is the bot). `BOT_BRANCH_PREFIX` and `PR_LIST_LIMIT` name the shape and bound.
- `tests/test_issue_implementer.py` — the fake `gh` answers `pr list`; the numerator test asserts the query; a
  new case proves a human's PR and another day's PR do not count.
- README — the cap paragraph states what is counted and why the login never was it.

## Verification

- `pytest tests/test_issue_implementer.py` → 29 passed.
- `python3 scripts/issue_implementer.py count --repo asimov-agent/llgenie --today 2026-10-19` → 0 (no
  `agent/issue-*` PR that day — correct: the engine-bump PRs are not the issue-bot's), and the live
  `gh pr list --json headRefName,author,createdAt` shape returns the repository's PRs.
- `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=issue-bot-cap-by-branch`,
  `make test-unit`.

## Honest limits

- The cap cannot be observed tripping until the bot actually opens three `agent/issue-*` PRs in a day; the
  numerator's behaviour is locked by the fake-`gh` argv test instead.
- The implementer still picks nothing today: no open issue carries `agent:implement` / `agent:ready`. That is
  the label gate, not a defect.
- `issue_refiner.py`'s cap was never affected (it counts the `agent:refined` label).
