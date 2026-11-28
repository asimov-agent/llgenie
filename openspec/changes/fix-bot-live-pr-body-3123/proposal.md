# fix-bot must check the LIVE PR body (#3123)

`fix-bot.yml` stamped `PR_BODY` only in the final outcome step, after the verdict. Body-dependent
gates therefore read an unset path, passed vacuously, and the bot posted a false `fixed` marker with
an unchanged head (PR #3122, runs `46132980221` / `46133842812`).

## Why

A green produced without the artefact it claims to measure is worse than a red: the board records a
repair that never happened and the reviewer stops looking.

## What changes

- Fetch `body`, `headRefOid` and `baseRefOid` from the live PR before `fix-loop-image`, into
  `fix-bot-pr-body.md` and step outputs.
- Pass `PR_BODY`/`PR_HEAD`/`PR_BASE` into the check loop.
- Refuse a body-dependent check whose live body or head/base is empty, with `exit=2`, before any
  `bot-done ... fixed` marker can be written.

## Capabilities

- New capability: `fix-bot-live-pr-body`
- Modified requirement: body-dependent fix-bot checks SHALL read the live PR body, not a stale stamp.
