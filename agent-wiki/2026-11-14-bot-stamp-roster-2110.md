# 2026-11-14 — the architecture bot stamps its own PR body (issue #2110, PR #PRNUM)

## What was verified

- Issue #2110's live finding held: architecture bot PR bodies carry no `AGENTS:`/`BASE:` pair.
  `render_pr` never imported `bot_preflight` and `publish` never called `stamp_body`, while the
  hygiene gate judged every architecture PR. The pair had to be *remembered*; this lane makes it
  impossible to forget.
- `render_pr` now returns `bot_preflight.stamp_body("\n".join(...), record)` — the same call
  `security_bot.pr_body` makes — and `publish` resolves the preflight record with
  `bot_preflight.resolve_record(cwd)` + `bot_preflight.stamp_line(measure_agents_md(cwd), main_sha(cwd))`
  BEFORE `create_issue` runs, so no GitHub write happens while the pair is unmeasured.
- `stamp_body` is append-at-end: the pair sits adjacent, flush-left, last, after `closes #<issue>`.
- `stamp_line`'s sha argument is a ref (it runs `git rev-parse`), not a literal 40-hex — the call
  passes `main_sha`.
- `tests/test_bot_stamp_body.py` derives the producer roster from the Makefile: python call sites
  (a bare `stamp_body(` in the first 3000 chars fails — only `bot_preflight.stamp_body` composes)
  plus a comment-stripped scan of the workflow producers' run blocks. Derived producers missing the
  qualified call exit 1 naming them; a stray call without a Makefile target exit 1 naming it. The
  architecture bot cannot leave the roster silently, and it is in the roster via
  `make architecture-bot`.
- Focused suite `tests/test_architecture_bot.py` + `tests/test_bot_stamp_body.py`: 34 passed, rc=0
  (host venv), including `test_publish_stamp_pair_passes_the_gate_that_judges_it` (the composed
  body fed to `check_pr_hygiene.pr_agents_line_findings` answers `["agents-line"]`-clean),
  `test_publish_refuses_before_any_write_when_main_is_unmeasurable` (zero gh calls when no ref
  resolves), and `test_an_unstamped_new_producer_reds_the_derived_roster`.

## Key decisions

- The record is measured from the repo root at run start (the lane's own checkout), not at open
  time: `stamp_body` measures the rulebook from the first ref that resolves (`origin/main` first),
  matching #2050's contract.
- `render_pr(issue, ..., *, commit="", record)` — `record` is a required keyword, so neither call
  site can compose an unstamped body.
- The stamp is a composition-time fact, so the dry preview, the published body, and the gate's own
  `pr_agents_line_findings` all see the same pair.

## Current status

OpenSpec change `bot-stamp-roster-2110` validated; the lane is one commit on
`feat/bot-stamp-roster-2110` closing #2110.
