---
name: lint-linefeeds-both-classes
about: lint_linefeeds reports BOTH failing classes (trailing newline and markdown blank-line) before returning 1
status: active
---

# lint_linefeeds reports both failing classes before returning (issue #1081)

## Proposal

`make lint` (via `scripts/lint_linefeeds.py check`) reports two independent classes of defect
against tracked text files:

- a file whose last line does not end in a trailing newline (the `trailing-newline` class), and
- a markdown file where a heading (`#`-level) is immediately preceded by non-blank content
  without a blank line (`markdown-heading` class).

The original `check()` returned `1` as soon as the trailing-newline class produced a finding, before
the markdown-heading report ran. A file failing BOTH classes (no trailing newline **and** a
heading-after-content) therefore reported only the newline defect and masked the markdown one: fixing
the newline and re-running is what finally surfaced the heading, so a single lint result was wrong by
omission and cost the reader a second CI matrix.

This change makes `check()` accumulate both classes before deciding:

- it prints the `trailing-newline` report when that class found a defect;
- it prints the `markdown-heading` report when that class found a defect;
- the `failed` flag is set when either class found a defect, and `check()` returns `1` only after both
  reports have printed (a single `if failed: return 1` at the end);
- a clean file still reports the aggregate OK and returns `0`.

## Motivation

A lint gate that reports only the first of two independent defects is wrong by omission and hides
work. The issue's own suggested fix is exactly this accumulate-both-then-return form, and it keeps
every class green independently (a file with only a newline defect, or only a markdown defect, still
exits 1 with its single report).

## Change

`scripts/lint_linefeeds.py`: `failed = False` accumulator; the `trailing-newline` block prints and sets
`failed` when `bad`; the `markdown-heading` block prints and sets `failed` when `md_bad`; a single
`if failed: return 1` at the end. `tests/test_lint_linefeeds.py`: two acceptance tests — one fixture
failing BOTH classes prints BOTH headers and exits 1 (and would have failed before this change by
printing only the trailing-newline report), and one clean-file test still exits 0 via the aggregate OK.
No new gate, no workflow, no Makefile change; only the reporting logic and its test.

`agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` re-rendered with `make changes-index`.
`openspec/changes/` change.
