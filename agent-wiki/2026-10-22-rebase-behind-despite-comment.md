# A comment is not a claim

Issue: #501. PR: #502.

The rebase sweep skipped #498 while it was behind `main` and conflicting, because a person's status
comment (`make test-unit passed`) was read as another bot holding the PR. Run `39719126900` printed
`pass-over: #498 is held by another bot: commented on by andyholst 90 min ago without a done comment`.

`scripts/bot_claims.py` now holds a subject only for a `bot-claim` marker from another bot, or a
`bot-done` marker whose outcome still occupies it. A plain comment holds nothing, so a PR that is
`BEHIND` or `DIRTY` is rebased on the next sweep.
