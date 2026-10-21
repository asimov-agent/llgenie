# fix-rebase-bot-done-marker

## Why

Run `39559756082` (2026-10-21T07:06Z, on `main` after #454) decided nothing needed rebasing:

```
[rebase-bot] pass-over: #446 was already rebased today
[rebase-bot] pass-over: #447 was already rebased today
[rebase-bot] pass-over: #448 was already rebased today
action=none
```

#446 was never rebased — its rebase failed in run `39554922931` (the agent could not resolve the
conflict, nothing was pushed). It was counted because the bot's own **claim** comment contains
`rebase-bot` followed by today's date, and `rebased_today()` matched any comment that way:

```
<!-- bot-claim: rebase-bot 2026-10-21T06:22:00Z rebase ttl=30m run=39554922931 -->
```

The same line means a **failure** comment counts too: `scripts/rebase_bot.sh`'s `comment()`
appends `done_comment(REBASER, now, "rebased")` to every outcome, including the "could not
resolve the conflict" and "structural checks failed" paths. So a failed attempt records the PR as
done for the rest of the UTC day and blocks the retry.

Issue: [#457](https://github.com/asimov-agent/llgenie/issues/457).

## What Changes

- `scripts/rebase_bot_sweep.py::rebased_today` reads the thread with `bot_claims.DONE_RE` and
  counts a PR only when the marker is this bot's, dated today, kind `rebased`. A claim, a
  pass-over, or a `gave-up` marker does not count.
- `scripts/rebase_bot.sh`: `comment()` takes the kind, `rebased` only on the success path and
  `gave-up` on every failure path (agent failed, `rebase --continue` failed, conflict markers
  remain, structural checks failed).
- Tests: the fixture that wrote `<!-- rebase-bot: <date> -->` (the shape that hid this bug) is
  replaced with real `bot-claim` / `bot-done` markers, and three cases pin claim-only,
  `rebased`, and `gave-up`.

## Impact

- Affected specs: `rebase-bot-sweep` (modified).
- Affected code: `scripts/rebase_bot_sweep.py`, `scripts/rebase_bot.sh`,
  `tests/test_rebase_bot_sweep.py`, README's rebase-bot section, `agent-wiki/` entry.
- No change to the merge state logic (#453) or to the push path.

## Not covered

- The claim on #446 (and the failed day it recorded) is not rewritten: it clears with the UTC
  date. No data migration is part of this change.
