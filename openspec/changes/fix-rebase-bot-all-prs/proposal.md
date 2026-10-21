# fix-rebase-bot-all-prs

## Why

The bot rebases **one** PR per run by design, so a moving `main` keeps re-dirtying the rest while
the bot sleeps six hours. Measured right after run `39581262100` (which rebased #446 to
`MERGEABLE`):

```
446 MERGEABLE  BLOCKED  fix/bot-pr-body-from-run
447 CONFLICTING DIRTY    fix/bot-pr-token-split
448 CONFLICTING DIRTY    fix/bot-scratch-ignored
```

#447 and #448 were never touched — the run ended after its single PR, and by the next slot `main`
had moved again (#458/#461), re-dirtying what had already been fixed. A backlog can never drain.

Issue: [#462](https://github.com/asimov-agent/llgenie/issues/462).

## What Changes

- `.github/workflows/rebase-bot.yml`: the single decision + single actor steps become ONE loop that
  re-asks `make rebase-bot-sweep` after every rebase and acts on its answer until it says
  `none`/`cap`, bounded by a new `max_prs` dispatch input (default 10). A PR whose rebase fails is
  aborted (`make rebase-bot-abort`) so the next decision runs on a clean tree, counted, reported,
  and does not stop the rest; the step exits non-zero when any picked PR failed.
- Makefile: `rebase-bot-abort` — abort a stopped rebase and return the tree to `main`.
- Tests: the workflow has the loop, the bound, the abort path and the failure exit; the target
  exists and is documented.

## Impact

- Affected specs: `rebase-bot-sweep` (modified — the run drains the backlog).
- Affected code: `.github/workflows/rebase-bot.yml`, `Makefile`, `tests/test_rebase_bot_sweep.py`,
  README's rebase-bot section, `agent-wiki/` entry.
- Unchanged: the decision itself (still `scripts/rebase_bot_sweep.py`), the conflict agent, the
  `done`/claim markers, the daily cap, the cron.

## Not covered

- The cron cadence and `MAX_PER_DAY` are not changed here.
- Parallel rebases (one job per PR) are not introduced: the PR branches share one checkout, and the
  bots' claim protocol is per PR, not per run.
