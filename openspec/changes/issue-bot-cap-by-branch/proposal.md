# The issue-bot's 3-per-day cap counts its own PRs

## Why

`scripts/issue_implementer.py::count()` is the cap's numerator, and it counted PRs `--author
github-actions[bot]`. The issue-bot does not open PRs as that login: `issue-bot-open-pr` runs `gh` with
the owner PAT, so its PRs are authored `asimov-agent`. The cap therefore read 0 whatever the bot did —
the "hard bound" in `issue-bot.yml`'s header was never enforced (issue #409).

Measured 2026-10-20: `gh search prs --author 'github-actions[bot]'` → `[]`; the bot-opened PRs on
2026-10-19 are authored `asimov-agent`. (Those particular seven were engine-bump PRs, which must not
count here — which is exactly why the fix cannot be "count the PAT owner" either.)

## What Changes

- **`scripts/issue_implementer.py`** — `count()` lists the repository's PRs and counts one when it was
  created today AND its head branch carries the dispatcher's `agent/issue-` prefix (or, defensively, its
  author is the bot). `BOT_BRANCH_PREFIX` names the shape; `PR_LIST_LIMIT` bounds the read.
- **`tests/test_issue_implementer.py`** — the fake `gh` answers `pr list` with branch + author +
  createdAt; the numerator test asserts the query, and a new case proves a human's PR and a PR from
  another day do not count.
- **README** — one line: the cap counts the dispatcher's own branch shape, not a login.

## Impact

- Affected specs: `issue-bot-cap` (new capability).
- Affected code: `scripts/issue_implementer.py`, `tests/test_issue_implementer.py`, `README.md`,
  `agent-wiki/`.
- No behaviour change on a day the bot opens nothing; the cap starts enforcing on the first day it does.

## Not covered

- `scripts/issue_refiner.py`'s own cap is fine: it counts the `agent:refined` label it applies, never an
  author.
- The implementer picks nothing today because no issue carries `agent:implement` / `agent:ready` — that is
  the label gate working, not this defect.
