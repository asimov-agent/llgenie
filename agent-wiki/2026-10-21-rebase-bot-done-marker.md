# 2026-10-21 — rebase-bot reads its DONE marker, not any comment (issue #457)

## What was wrong

Run 39559756082 (07:06Z, on `main` *after* #454) decided nothing needed rebasing:

```
[rebase-bot] pass-over: #446 was already rebased today
[rebase-bot] pass-over: #447 was already rebased today
[rebase-bot] pass-over: #448 was already rebased today
action=none
```

#446 was never rebased — its rebase failed in run 39554922931 (the agent could not resolve the
conflict, nothing was pushed). `rebased_today()` matched any comment containing `rebase-bot`
followed by today's date, so the bot's own claim counted:

```
<!-- bot-claim: rebase-bot 2026-10-21T06:22:00Z rebase ttl=30m run=39554922931 -->
```

`scripts/rebase_bot.sh` also appended `done_comment(REBASER, …, "rebased")` on every path,
including the failure paths — so a failed attempt recorded the whole UTC day as done.

## What changed

- `scripts/rebase_bot_sweep.py::rebased_today` parses `bot_claims.DONE_RE` and counts a PR only
  for this bot's marker, dated today, kind `rebased` (`_rebased_marker`). `MARKER`/`import re` are
  gone with the regex.
- `scripts/rebase_bot.sh`: `comment()` takes the kind (`rebased` on the push path, `gave-up` on
  every failure path).
- The test fixture that wrote `<!-- rebase-bot: <date> -->` (the shape the buggy regex matched) is
  replaced with real `bot-done` markers, which is what let this bug hide.

## Verified

- `tests/test_rebase_bot_sweep.py` 27 passed: claim-only is not the record, `rebased` is,
  `gave-up` is not, and the actor's success path alone passes `rebased`.
- Read-only run of the fixed sweep against `asimov-agent/llgenie` now picks #446 instead of
  reporting it "already rebased today" (see the PR body).

## Status

OpenSpec change `fix-rebase-bot-done-marker`; issue #457; PR #458 from `feat/rebase-bot-marker`
against `asimov-agent/llgenie:main`. Waiting for review — the agent never merges.
