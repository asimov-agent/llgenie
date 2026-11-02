# 2026-11-02 — issue #1081: lint_linefeeds reports both failing classes before returning

## What was wrong

`scripts/lint_linefeeds.py check()` — the gate behind `make lint` and the CI lint job — reports two
independent classes of defect against tracked text files: a missing trailing newline
(`trailing-newline`) and a markdown heading immediately preceded by non-blank content without a blank
line (`markdown-heading`). The original code returned `1` as soon as the trailing-newline class found a
defect, before the markdown-heading report ran. A file failing **both** classes therefore reported only
the newline defect and masked the heading one — fixing the newline and re-running is what finally
surfaced the heading, so a single lint result was wrong by omission and cost the reader a second CI
matrix.

## What the change is

`check()` now accumulates both classes before deciding:

- it prints the `trailing-newline` report when that class found a defect (`failed = True`);
- it prints the `markdown-heading` report when that class found a defect (`failed = True`);
- the `failed` flag is set when either class found a defect, and `check()` returns `1` only after both
  reports have printed — a single `if failed: return 1` at the end (the issue's exact suggested form);
- a clean file still prints the aggregate OK line and returns `0`.

This keeps every class green independently: a file with only a newline defect, or only a markdown
defect, still exits 1 with its single report; a file failing both names both in one run.

## Proof

Measured in this worktree (fixtures under `tests/test_lint_linefeeds.py`, venv
`/home/asimov/.cache/pytest-venv`, `TMPDIR=/home/asimov/.cache/tmp`):

- both-class fixture `b"Some body text\n## A heading right after content"` (no trailing newline and a
  heading not preceded by a blank line): `check()` prints the `trailing-newline` header AND the
  `markdown-heading` header and exits 1 — before this change it printed only the trailing-newline
  report;
- the two acceptance tests pass with `python3 -m pytest tests/test_lint_linefeeds.py -q` (17 passed);
- `make lint`, `make check-docs` and `make check-pr-hygiene` are green at this head.

Issue: #1081
