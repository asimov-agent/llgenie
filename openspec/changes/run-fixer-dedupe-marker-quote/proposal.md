# The run-fixer dedupe marker must survive a quoted workflow name

## Why

`scripts/run_failure_reactor.py::filed()` dedupes a run-fixer issue by searching for its body
marker: `gh issue list --search '"<marker>" in:body'`. The marker is
`<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` — and for the `ci-verdict` workflow the `WORKFLOW`
display name literally contains a double-quote (`ci-verdict — holds a finished CI run to its
published scope decision, and says "no verdict" out loud`, `.github/workflows/ci-verdict.yml:1`).
GitHub search cannot express a double-quote inside a quoted phrase, so the exact-phrase query
**never matches** and a duplicate issue is filed for the same `head+job+step` on every failing run.

Measured at `main` `05185f9a` (issue #1990): the run-failure reactor filed **13 issues for one
head+job+step** (#1970 #1971 #1973 #1974 #1975 #1977 #1978 #1980 #1983 #1984 #1985 #1987 + #1990),
all carrying the same marker. Live read: the exact marker returns 0 issues; the same marker with the
`"` stripped returns 9. The dedupe memory never matched, so every failing judge run became a new
duplicate.

## What Changes

- **`scripts/run_failure_reactor.py::filed()`** — build the search query from the marker with the
  double-quote characters removed. GitHub's search index treats punctuation as a separator, so a
  body holding `says "no verdict" out loud` is matched by the phrase `says no verdict out loud`;
  stripping `"` from the query phrase makes it find the marker exactly as it was written. One local
  change to the one search.
- **`tests/test_run_failure_reactor.py`** — the `gh` stub's `issue list` branch models GitHub's
  quoted-phrase rule (a phrase split by an embedded `"` cannot match); a new regression test drives a
  workflow whose display name contains a double-quote and asserts nothing extra is filed when a sibling
  issue already carries the marker.
