# A PR behind main is rebased even when someone commented on it

## Why

The rebase sweep refused PR #498 while it was behind `main` and conflicting. Run `39719126900` printed:

```
[rebase-bot] pass-over: #498 is held by another bot: commented on by andyholst 90 min ago without a done comment
action=none
```

The comment was a status note (`make test-unit -> 5006 passed`), posted by a person, with no `bot-claim` marker. `scripts/bot_claims.py` treats the newest comment from anyone as a hold for the claim TTL, so a human note freezes a branch that `main` has moved past. The sweep's own rule says a conflicted PR is taken, because the rebase is the fix. The comment check runs first and wins.

## What Changes

- **`scripts/bot_claims.py`** — a comment holds a subject only when it carries a `bot-claim` marker from another bot, or a `bot-done` marker whose outcome still occupies the subject. A plain comment, from a person or from a bot, holds nothing.
- **`tests/test_rebase_bot_sweep.py`** — a behind/conflicting PR with a plain comment is rebased; a real claim marker still holds it.
- **`README.md`, `agent-wiki/`** — record the rule.

## Impact

- A PR that is `BEHIND` or `DIRTY` against `main` is rebased on the next sweep, however many status comments it carries.
- A live claim marker still stands the rebase bot down, so it does not rewrite a branch another bot is repairing.
