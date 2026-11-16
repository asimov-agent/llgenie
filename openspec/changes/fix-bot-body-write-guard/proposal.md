# fix-bot-body-write-guard — proposal

Issue: the fix-bot body-write guard (filed off PR #2113, implementing #2112); an agent:implement issue.

## Why

`fix-bot` pushes a repair commit and, in the same act, replaces the PR **body**. When the body it
writes back is the pre-fix copy, it silently deletes work another lane put there — measured twice on
PR #2113 (heads `ae4bb883`, `84b68fd7`), and each deletion re-redded the same gate the lane had just
cleared (`ci-scope` `[check-pr-acceptance] 2 violation(s)`, runs `42448318954`/`42449007827`, green on
rerun when the lane re-applied the body). `check-pr-acceptance` reads the LIVE PR body by design
(issue #1589), so anything a lane records there — `## Not covered` exemptions, `(proven: …)` ticks —
is load-bearing state. A bot that regenerates the body from a template derived before that state
existed turns a green gate red on the next push, costs a rerun cycle, teaches the next lane that a
body fix does not stick, and silently reverts text a human reviewer may already have read.

## What Changes

- **`scripts/bot_preflight.py`** — the ONE body-stamp authority (issue #2050) gains the conditional
  write guard:
  - `protected_items(text)` – the load-bearing content a bot write must never drop: every `## `
    heading (a section e.g. `## Not covered`) and every ticked `- [x]` line carrying a
    `(proven: …)` marker. Matching reuses the `## `/`##` heading shape the gates already parse
    (`scripts/issue_body.py`, `scripts/acceptance_writeback.py`), never a restated copy.
  - `body_write_guard(live, proposed)` – the list of protected items `live` carries that `proposed`
    would silently drop; non-empty means the write must be refused.
  - `stamp_body` enforces the invariant itself (a re-stamp may only touch the `AGENTS:`/`BASE:`
    pair; it never drops a section or a proven tick).
  - `--guard-live`/`--guard-proposed` CLI mode: exit 0 when writing `proposed` is safe, 1 (non-zero
    through make) and prints the refused items when it would drop content.
- **`make bot-body-guard`** (new, in `mk/bots.mk`, `.PHONY` in the top Makefile) — the workflow-facing
  gate: `LIVE=`/`PROPOSED=` files in, exit 0 = safe to write, non-zero = would drop.
- **`.github/workflows/fix-bot.yml`** — the re-stamp step now reads the LIVE body, re-stamps only the
  `AGENTS:`/`BASE:` pair, then runs `make bot-body-guard` before any `gh pr edit`. When the guard
  refuses it does NOT write the body — it logs the skip and posts a PR comment naming the section/it
  was about to drop, so the lane that owns the body sees the decision.
- **`tests/test_bot_stamp_body.py`** — regression tests: the guard refuses a rewrite that would drop
  `## Not covered` (AC1/AC3), the re-stamp preserves the section and its `- [x] (proven: …)` items
  (AC2), the workflow runs the guard before `gh pr edit` and comments on a refusal (AC3), and the
  target is wired/phony/documented.

## Not covered

- The planner lane's own `## Not covered`/`(proven: …)` write-back paths are untouched — only a bot
  body-write is made conditional here. A finding that another lane rewrites a body it did not author
  is its own issue.
- `make openspec-validate` for this change could not run in this container (no Docker daemon); the
  gate is exercised in CI where the OpenSpec CLI runs.
