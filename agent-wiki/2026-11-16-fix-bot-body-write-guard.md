# 2026-11-16 — a bot body-write never drops a lane's `## Not covered` / `(proven: …)` evidence

**Issue:** agent:implement · **OpenSpec:** `fix-bot-body-write-guard` ·
**Related:** #2113, #1589, #1644, #2050, #2112

## What was measured

`fix-bot` pushes a repair commit and, in the same act, replaces the PR **body**. When the body it
writes back is the pre-fix copy, it silently deletes work another lane put there — measured twice on
PR #2113 (heads `ae4bb883`, `84b68fd7`), and each deletion re-redded the same gate the lane had just
cleared (`ci-scope` `[check-pr-acceptance] 2 violation(s)`, runs `42448318954`/`42449007827`, green
on rerun when the lane re-applied the body). `check-pr-acceptance` reads the LIVE PR body by design
(issue #1589), so anything a lane records there — `## Not covered` exemptions, `(proven: …)` ticks —
is load-bearing state. The rewrite is not visible as a diff, and the lane whose evidence was deleted
learns it from a red gate on a head it already fixed, which is what re-dispatches `fix-bot`.

## What changed

- `scripts/bot_preflight.py` (the ONE stamp authority, #2050):
  - `protected_items(text)` — every `## ` heading and every ticked `- [x] (proven: …)` line, using the
    same heading/proven shapes the gates already parse (`issue_body`, `acceptance_writeback`);
  - `body_write_guard(live, proposed)` — the protected items `live` carries that `proposed` would drop;
  - `stamp_body` enforces the invariant (a re-stamp may only touch the `AGENTS:`/`BASE:` pair);
  - `--guard-live` / `--guard-proposed` CLI mode (exit 0 safe, non-zero + prints the refused items).
- `make bot-body-guard` (new, `mk/bots.mk`, `.PHONY`) — the workflow-facing conditional write gate.
- `.github/workflows/fix-bot.yml` — the re-stamp step runs `make bot-body-guard` before `gh pr edit`;
  on a refusal it leaves the live body untouched, logs the skip, and posts a PR comment naming the
  section it refused to drop (so the lane that owns the body sees the decision).
- `tests/test_bot_stamp_body.py` — regression: the guard refuses a would-drop of `## Not covered`
  and a `(proven: …)` tick; the re-stamp preserves the section and its ticks; the workflow runs the
  guard before `gh pr edit` and comments on a refusal; the target is wired/phony/documented.

## Verification

- `tests/test_bot_stamp_body.py`: 18 passed.
- Targeted regression set (`test_bot_preflight_base_line`, `test_acceptance_writeback`,
  `test_engine_bump_pr_body`): 52 passed.
- `python3 scripts/check_workflows.py check`: green (fix-bot.yml parses).
- Live `make bot-body-guard` over temp fixture files: refuses a would-drop (exit non-zero, names
  `heading: Not covered`), and passes a preserving re-stamp (exit 0).

## Decisions

- The gate is untouched. Weakening `check-pr-acceptance` would turn the red green and leave the class
  of defect in place; the bot's WRITE is made conditional instead.
- A refusal is reported on the PR (a comment naming the refused item) rather than silently skipped,
  because a lane whose body survives must still be able to see the bot honoured it.
- `make openspec-validate NAME=fix-bot-body-write-guard` could not run in this container (no Docker
  daemon, no node for the CLI); the OpenSpec change is authored in the CLI's shape and its gate is
  exercised in CI where the Dockerized CLI runs.
