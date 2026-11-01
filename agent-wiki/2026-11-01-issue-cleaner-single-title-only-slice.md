# 2026-11-01 — issue-cleaner: a single title-only merged PR no longer closes a tracking issue (#1413)

Change record for `scripts/issue_cleaner.py` + `docs/BOTS.md` (merged as #1460 → `2ae46fb8`,
closes #1413). This note is the missing change-record the merged head itself lags — filed via
#1463 after CI's `check-docs` `change->note` red (#1123) measured the behavioural `BOTS.md`
help-text edit without its note; this trio lands the record on current main (no rebase of the
merged #1460, issue #1413 stays COMPLETED).

## What and why

`make issue-cleaner-apply` previously closed a tracking issue when ANY merged-to-main PR whose
title alone matched it (a "title-only" match) resolved it. That over-closed: a single title-only
PR whose body carries no adjacent closing keyword is often a **slice** of a larger effort — an
issue someone intends to build out — not a completed implementation. Only a body GitHub itself
parsed as closing (an adjacent `Closes #N` / `Fix #N` on its own line, per `check-pr-closing`'s
regex) should close; a title-only match is demoted to a hold (left open, reported).

## The change

- `scripts/issue_cleaner.py`: new `demote_title_only_slices()` pass, run in `scan()` *after*
  `demote_shared_title_vehicles()`. Every surviving single title-only close (evidence == "the
  title") is demoted to action `slice`; `main()` holds `("audit", "vehicle", "slice")` and never
  closes a `slice`. A body GitHub parsed as closing still closes; shared-title tracking vehicles
  and `Issue:`-line commits are never demoted.
- `docs/BOTS.md` (`issue-cleaner-apply` help-text, ~2056): names the single title-only slice hold
  alongside the shared-title vehicle hold (issues #1413, #1414).
- `tests/test_issue_cleaner.py`: 2 new hermetic tests + the #952 control given a real `Issue:`
  commit line; `pytest tests/test_issue_cleaner.py` = 21 passed.

## Proof

- Merged on main at `2ae46fb8` ("ci(issue-cleaner): a single title-only merged PR no longer closes
  a tracking issue (#1413) (#1460)"); head `2c7cbac3`.
- `check-docs` green at the PR head in CI (scope job `41350831515`; the pre-merge `41350831447`
  red on this BOTS.md edit is exactly the missing-note violation this trio lands).
- This note + `docs/changes.d/2026-11-01-issue-cleaner-single-title-only-slice.md` + regenerated
  `CHANGES.md` satisfy the `change->note` rule (issue #1123) on current main.

Branch `fix/1463-change-record`; PR closes #1463 (not #1413).
