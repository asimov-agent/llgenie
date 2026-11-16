# A bot's PR-body write is guarded by the live body it would overwrite (issue #2131)

## Why

`check-pr-acceptance` reads the LIVE PR body by design (issue #1589), so anything a lane records there —
`## Not covered` exemptions, ticked `- [x]` items with `(proven: …)` evidence — is load-bearing state.
Measured twice on PR #2113 (heads `ae4bb883`, `84b68fd7`): a fix-bot repair push replaced the body with its
own pre-fix copy, deleting the lane's `## Not covered` section and its three proven-ticked items, and each
deletion re-redded `ci-scope` (`[check-pr-acceptance] 2 violation(s)`, runs `42448318954`, `42449007827`)
on a head the lane had already fixed. The rewrite is invisible as a diff — a commit shows files; the body
changes outside the commit — and the red it creates re-dispatches the bot, so the two behaviours feed each
other.

## What changes

- `scripts/pr_body_write.py` is the guarded body-WRITE seam every bot leg routes a body update through:
  it reads the LIVE body through `gh`, compares it with the body it is about to write, and skips the write
  when the live body carries content the proposed body drops — a heading the proposal lacks, or a ticked
  `- [x]` line carrying `(proven:` the proposal lacks. A skip logs the reason and posts a PR comment naming
  each section it refused to drop; an equal body writes nothing; a content-preserving rewrite proceeds.
- `make bot-body-write PR=<n> REPO=<r> NEW=<body file>` is the one shell entry to the seam.
- `fix-bot.yml`'s re-stamp step stops hand-rolling `gh pr edit`: it stamps the fetched body with the
  preflight pair (unchanged from #2050) and hands the result to `make bot-body-write`.
- `tests/test_pr_body_write.py` drives the seam over a fixture whose live body carries a lane's
  `## Not covered` section with proven-ticked items, proposes the pre-fix copy, and asserts the section
  survives, no `gh pr edit` happened, and the skip comment names the section.
- `docs/BOTS.md` records the seam; a changes.d row and an agent-wiki entry close the loop.

## What does not change

`bot_preflight.stamp_body` keeps its #2050 role — the stamp authority for the `AGENTS:`/`BASE:` pair. This
change adds the write-side guard around every body replacement, not a second stamper. PRs OPENED by a bot
(`gh pr create` from a body the bot authored) are unchanged: the guard governs writes to a body the bot
did not author in this run.

## Impact

Affected specs: `bot-body-write-guard` (new). Affected code: `scripts/pr_body_write.py` (new),
`mk/bots.mk`, `Makefile` (`.PHONY`), `.github/workflows/fix-bot.yml`, tests, docs. No gate is weakened;
no engine, model or inference-server behaviour moves.
