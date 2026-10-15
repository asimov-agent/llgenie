# The bot-slot isolation guard derives its scope from the workflows (issue #301)

**Issue:** [#301](https://github.com/asimov-agent/llgenie/issues/301)
**Capability:** `bot-slot-isolation`

## Why

`#275` pinned one rule: **no two bots own the same `(minute, weekday)` cron slot**. It enforced that
with a hand-kept tuple of six workflow filenames. Three scheduled bots were merged afterwards —
`rebase-bot` (#246), `issue-refiner` (#264), `code-review-bot` (#269) — and were therefore **outside
the guard entirely**.

So the guard passed while the collision it exists to prevent was live:

```
minute 23, weekday 1: owned by both code-review-bot.yml and issue-bot.yml
minute 23, weekday 1..6: owned by both issue-bot.yml and rebase-bot.yml
```

`issue-bot` (`23 6 * * *`) and `rebase-bot` (`23 */6 * * *`) both start at **06:23 UTC every day** —
exactly the failure `#271`/`#272` were filed for. Measured on `a6ec098`: the shipped guard passes
(3 passed); the *same guard* with those three bots added to its list fails (1 failed, 2 passed).

The structural defect is the scope, not the two crons: a guard whose bot set is a hand-written list
**cannot fail** for a bot nobody listed, so it silently stops protecting anything and every new bot
lands outside it unless someone remembers to edit a tuple.

## What Changes

- **`tests/test_bot_pipeline_isolation.py`** — the bot set is now **derived from the tree**: any
  workflow under `.github/workflows/` that declares a `schedule:` is a bot and is held to the slot
  and concurrency rules, whether or not this module mentions it. The every-hour bots' reserved
  minutes are derived the same way (from the crons themselves, not a literal set), so a new
  every-hour bot reserves its minute automatically.
- **A regression test for the scope itself** — `BOT_WORKFLOWS` must equal what the filesystem
  yields, so re-introducing a narrowed list fails the suite (that is how #301 happened).
- **The two colliding crons are re-staggered**: `rebase-bot` `23 */6 * * *` -> `29 */6 * * *`,
  `code-review-bot` `23 7 * * 1` -> `31 7 * * 1`. `issue-bot` keeps `:23`.
- Their header comments and the `README.md` mention carry the new minutes.

## Impact

Every scheduled bot now owns a unique minute: `7, 17, 19, 23, 29, 31, 37, 41, 43, 53`. The only
behaviour change is *when* `rebase-bot` and `code-review-bot` fire (a few minutes later, on the same
cadence); neither loses a run and both keep `cancel-in-progress: false`.

## Not covered

- `#276` (a self-documenting dispatch form per bot) — separate.
- Making the slot rule a runtime mutex; it stays a static schedule check.
- De-duplicating runs inside GitHub's own scheduler.
