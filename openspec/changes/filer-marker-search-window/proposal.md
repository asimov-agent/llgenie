# filer-marker-search-window

## Why

Issue #2848: `scripts/registry_change_issue.py::open_issue` hunts its own dedupe marker
(`<!-- registry-sync-changes: <utc> -->`) through `gh issue list --state open --limit 100` —
a newest-first page of 100. Measured 2026-11-16: the open board spans #2845..#2738 in that page,
and the marker-bearing issue #2659 sits at open-list position 110. The filer therefore forgot an
issue it had itself filed and created the duplicate #2847 for the same store. A producer's memory
of what it filed silently depends on how many issues happen to be open elsewhere.

## What Changes

- **ADDED**: marker-keyed issue dedupe resolves through GitHub issue **search**
  (`in:body` query for the exact marker, `state:open`) instead of a truncated listing, so the
  hit is found wherever it sits in the open board. Applied to
  `scripts/registry_change_issue.py::open_issue`.
- **PRESERVED**: the semantics after a hit — REST body update (issue #2673 path), label re-queue
  when the `agent:implement` label is missing (#724) — and the create path when the search
  returns nothing (create once, label via REST, exactly as today).

## Out of scope (filed separately, linked)

- The pairwise dedupe bots' capped open scans (`scripts/issue_dedup.py`, `scripts/issue_cleaner.py`,
  `--limit 200`) are the same class but need a paginated full scan, not a body search —
  filed as #2849 and labelled `parked`.

## Impact

- Affected code: `scripts/registry_change_issue.py` (dedupe lookup only).
- Affected tests: `tests/test_registry_change_issue.py` (mock seam for the gh calls) + the new
  window-overflow case.
- Affected docs: `agent-wiki/` entry + `docs/changes.d/` fragment naming #2848, #2847, #2659.
