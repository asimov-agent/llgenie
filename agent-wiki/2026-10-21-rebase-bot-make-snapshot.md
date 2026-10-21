# 2026-10-21 — rebase-bot reaches its conflict agent while the Makefile is conflicted (issue #460)

## What was wrong

PR #446 never reached the model. Run 39566967551 shows:

```
Auto-merging Makefile
CONFLICT (content): Merge conflict in Makefile
[rebase-bot] conflict: asking the agent to resolve it
Makefile:628: *** missing separator.  Stop.
[rebase-bot] agent failed
```

`scripts/rebase_bot.sh` invoked `make rebase-bot-agent` AFTER the conflicted checkout. GNU make
must parse `Makefile` before running any target, so a Makefile mid-rebase stops it — and the
recipe then ran `make _rebase-bot-agent` inside the container against the same file.

## What changed

- `scripts/rebase_bot.sh` snapshots `Makefile` **before** the checkout
  (`MK_SNAPSHOT="$(mktemp)"; cp Makefile "$MK_SNAPSHOT"`) and defaults the agent to
  `make -f $MK_SNAPSHOT rebase-bot-agent` — same target, from a file that still parses.
- `Makefile`: the `rebase-bot-agent` recipe runs `hermes -z "$(cat)" -m nous-deepseek
  --reasoning medium --yolo` directly inside the agent image (the shape `scripts/fix_loop.sh`
  uses); the dead `_rebase-bot-agent` target is gone.
- `tests/test_scrub_log.py`'s internal-target roster drops `_rebase-bot-agent` and instead
  asserts the public leg calls hermes inline and no internal target is back.

## Verified

- `pytest tests/test_rebase_bot_sweep.py tests/test_scrub_log.py` 39 passed.
- Gates and the full unit suite recorded in the PR.

## Status

OpenSpec change `fix-rebase-bot-make-snapshot`; issue #460; PR #461 from `feat/rebase-bot-make-snapshot`
against `asimov-agent/llgenie:main`. Waiting for review — the agent never merges.
