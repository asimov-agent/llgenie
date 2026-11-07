# run-fixer dedupe survives a quoted workflow name (issue #1990)

## What was verified

- `scripts/run_failure_reactor.py::filed_phrase(marker)` strips every `"` out of the marker
  before building the `--search` phrase; `filed()` uses it. A workflow display name like
  `ci-verdict — holds a finished CI run to its published scope decision, and says "no verdict"
  out loud` (`.github/workflows/ci-verdict.yml:1`) embeds a `"` that GitHub's search phrase
  cannot express, so the verbatim marker never matched and a duplicate issue was filed for every
  failing run — 13 issues for one `head+job+step` at origin/main@05185f9a.
- The `gh` stub in `tests/test_run_failure_reactor.py` now models GitHub's quoted-phrase rule:
  a query split by an interior `"` matches nothing; only a quote-free phrase reaches the marker
  match. The new `test_a_quoted_workflow_name_still_dedupes` drives a quoted workflow name
  through the full reactor and asserts the second run files nothing.
- Guard-negative proven: with the quote-strip reverted, the new test fails; with it restored,
  the full reactor suite is 23/23 green.

## Key decisions

- The judge was diagnosed as CORRECT-RED (the 9 failures each held a genuinely-red guard-failed
  PR run that published no scope decision; the single success held a green push). No judge code
  changed.
- The dedupe fix is one local change to the one search; it does not touch the marker format,
  so existing marker-bearing issues keep their memory.

## Status

Implemented on branch `wt/1990-ci-verdict-judge`; PR closes #1990.
