# Filer marker search window (2026-11-16)

Implements issue #2848. The registry-change filer (`scripts/registry_change_issue.py`)
found its own previously filed issue through `gh issue list --state open --limit 100`,
a newest-first page. Measured 2026-11-16: the open window spanned #2845..#2738 (100
issues) while the marker-bearing #2659 sat at open-list position 110 — the filer forgot
an issue it had filed itself and re-filed the same store as the duplicate #2847 (closed
as duplicate the same day).

## Decision

- Dedupe lookup is now a GitHub issue **body search** for the exact marker
  (`search/issues -f q='repo:<slug> "<needle>" in:body state:open'`), validated live
  against the real case: total_count 1, hit #2659, beyond the window.
- Search hits are confirmed by reading the issue body back and matching the exact
  marker; pull-request hits are filtered out.
- A failed search fails the step loudly — the filer files nothing blind (spec scenario).
- Update semantics unchanged: REST body PATCH (#2673), label re-queue (#724); create
  path unchanged for the search-miss case.
- Out of scope, filed as #2849: the pairwise dedupe bots (`issue_dedup.py`,
  `issue_cleaner.py`) cap their open scans at 200 and need a paginated full scan, not
  a body search.

## Verified

- `tests/test_registry_change_issue.py` extended: window-overflow case (>100 open,
  marker at position 108 finds `updated #2659`), failed-search case, PR-hit-filtered
  case; the two dry-run tests updated from "no api calls" to "reads allowed, writes
  none" (23 passed rc=0 at the fast seam).
