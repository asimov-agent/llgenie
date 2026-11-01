# 2026-11-01 issue cleaner: a single title-only merged PR no longer closes a tracking issue (#1413)

The issue cleaner (`scripts/issue_cleaner.py`) found, for a still-open issue, exactly one signal a
merged PR implemented it — an `Issue: #N` merge-commit line, a body GitHub parsed as closing, or the
PR title's trailing `(#N)`. The first two are strong (the merge commit's own hygiene rule, and
GitHub's own auto-close parse). The title was not: a tracking issue can have a single merged slice
that says `(#N)` in its title and still be unfinished, and the cleaner trusted that one title and
closed the issue (issue #1413). A scheduled close that trusts a single title treats a partial or
audit PR as the whole issue; the tracker reads "done" while the acceptance work is still open.

This change makes the title-only signal weak: `demote_title_only_slices()` in
`scripts/issue_cleaner.py` demotes every surviving single title-only close (evidence == "the title")
to action `slice` after `demote_shared_title_vehicles()`, `scan()` runs both demotions, and `main()`
reports `slice` in the held set (`audit` / `vehicle` / `slice`) and never closes it. A PR whose body
carried an adjacent close already populated `closingIssuesReferences` (`implemented_issue` returns
None), so by construction every title-only finding that reaches the demote lacked the adjacent-body
close the acceptance requires.

The two stronger signals still close: the merge-commit `Issue:` line, and a body GitHub parsed as
closing (which never leaves a finding). The shared-title-vehicle hold (#1079 via #1310/#1319) and the
idle-audit hold (#1282 via #1377) are unchanged. Reference: issue #1413 (acceptance criteria in
body); docs/BOTS.md `make issue-cleaner-apply` / `make issue-cleaner-scan` help text updated to name
the slice hold (issues #1413, #1414).
