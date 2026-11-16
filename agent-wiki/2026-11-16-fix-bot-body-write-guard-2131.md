# Fix-bot body-write guard (issue #2131)

Implements issue #2131: a fix-bot repair push that replaced PR #2113's body with its own pre-fix copy
deleted the lane's `## Not covered` section and three proven-ticked items — twice (heads `ae4bb883`,
`84b68fd7`), each time re-reddeing `ci-scope` (`[check-pr-acceptance] 2 violation(s)`, runs
`42448318954`, `42449007827`) on a head the lane had already fixed.

## What was built (verified against the OpenSpec change `fix-bot-body-write-guard`)

- `scripts/pr_body_write.py`: the guarded body-write seam. `body_preserve_findings(live, proposed)`
  names every live heading / ticked `(proven:` line the proposal drops; `write_body` reads the live body
  through `gh` (`proc.run_text`), skips a dropping write with a log + PR comment naming each item,
  writes nothing for an identical body, and reaches `gh pr edit` only for a preserving rewrite. A skip
  exits 0 — the skip is the correct outcome.
- `make bot-body-write PR=<n> NEW=<file> [REPO=]` (mk/bots.mk, `.PHONY` in the Makefile) is the one
  shell entry; `check-wiring` counts it.
- `.github/workflows/fix-bot.yml`: the re-stamp step (issue #2050) now ends in the seam; the `cmp`/edit
  dance is gone, and no hand-rolled body replacement is left in the repair path.
- `tests/test_pr_body_write.py`: five tests over a #2113-shaped fixture with `gh` stubbed on PATH; the
  stub's `pr edit` actually applies the proposal to a state file, so "the section survives" is state,
  not a string match. All five pass locally (0.27 s).

## Decisions

- Guard is textual and cheap (the issue's own metric): headings + proven-ticked lines, compared as
  stripped lines; live items must be a subset of the proposal's lines. Additions are always allowed.
- The seam does NOT govern PRs a bot OPENS (`gh pr create` with a body the bot authored this run) — only
  replacements of a body the bot did not author in this run (issue body rule 2).
- A refused write is loud (log + PR comment) but exits 0, matching the repo's "no-PR dispatch is a clean
  success" precedent (#2430): the bot did the right thing by not writing.

## Current status

Branch `feat/fix-bot-body-write-guard`; `make check-workflows` (incl. actionlint/shellcheck) and
`make check-wiring` green locally; full unit suite gated via `make test-unit` before push.
