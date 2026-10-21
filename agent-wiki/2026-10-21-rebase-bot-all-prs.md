# 2026-10-21 — one rebase-bot run drains every eligible PR (issue #462)

## What was wrong

The bot rebased ONE PR per run by design, so a moving `main` re-dirtied the rest while it slept.
Right after run 39581262100 (which rebased #446 to `MERGEABLE`):

```
446 MERGEABLE  BLOCKED  fix/bot-pr-body-from-run
447 CONFLICTING DIRTY    fix/bot-pr-token-split
448 CONFLICTING DIRTY    fix/bot-scratch-ignored
```

#447 and #448 were never touched; by the next slot `main` had moved again (#458/#461).

## What changed

- `.github/workflows/rebase-bot.yml`: the single decision + single actor steps became one loop that
  re-asks `make rebase-bot-sweep` after every rebase and acts until it says none/cap, bounded by a
  new documented `max_prs` dispatch input (default 10). A failed rebase calls
  `make rebase-bot-abort` (tree back on `main`), is counted and reported, and the loop continues;
  the step exits non-zero at the end naming the failures.
- `Makefile`: new `rebase-bot-abort` target (abort a stopped rebase, return to `main`), declared
  phony and documented in README.

## Verified

- `pytest tests/test_rebase_bot_sweep.py` 32 passed (loop + bound + stop condition, abort path and
  failure exit, the abort target and its wiring).
- `check-wiring`, `check-docs`, `check-workflows`, `check-dispatch-forms`, `check-pr-hygiene`,
  `check-pr-authors`, `lint` and `openspec-validate` exit 0; the full suite is recorded in the PR.

## Status

OpenSpec change `fix-rebase-bot-all-prs`; issue #462; PR #463 from `feat/rebase-bot-all-prs` against
`asimov-agent/llgenie:main`. Waiting for review — the agent never merges.
