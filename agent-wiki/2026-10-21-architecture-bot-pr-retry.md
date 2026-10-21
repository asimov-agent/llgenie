# 2026-10-21 — a lost GitHub answer no longer strands an architecture refresh (issue #479)

## What was wrong

The bot's second real run (`39620798522`, 15:00Z) proved the tool call, rewrote the doc, filed
issue #478, pushed `agent/architecture-20261021T1500` — and then GitHub's gateway answered the PR
create with **504**. The run went red and the refresh was stranded: open issue, pushed branch, no
PR.

## What changed

- `scripts/architecture_bot.py`: `_gh_retry` retries a GitHub write on a transient
  502/503/504/timeout (3 attempts); `publish` recovers a lost create by looking for an open PR on
  the branch it pushed (`open_pr_for_branch`); a real failure raises an error naming the issue
  number and branch.
- `tests/test_architecture_bot.py`: retry-after-two-504s, create-never-answers-but-PR-exists,
  and the real-failure message; the fake `gh` can now answer 504 and a per-branch PR lookup.

## Verified

- `pytest tests/test_architecture_bot.py` 14 passed.
- The stranded run was finished by hand as PR #480 (branch `agent/architecture-20261021T1500`,
  closes #478).

## Status

Issue #479; PR #481 from `feat/architecture-bot-pr-retry` against `asimov-agent/llgenie:main`. Waiting
for review — the agent never merges.
