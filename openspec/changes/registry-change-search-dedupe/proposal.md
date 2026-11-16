# registry-change-search-dedupe

## Why

`scripts/registry_change_issue.py::open_issue` hunts the marker it files (the store's
`generated_utc` wrapped as `<!-- registry-sync-changes: {utc} -->`) by listing the OPEN
issues newest-first and capping the listing at 100: the dedupe's memory of what it filed is
"position 1..100 of `gh issue list --state open --limit 100`". That memory silently depends
on how many issues happen to be open at the moment the lane runs.

Measured 2026-11-16: the weekly `registry-sync` lane re-filed the 2026-11-15T08:29:53Z store
review as #2847 even though #2659 already carried its exact marker. The open board spanned
#2845..#2738 (100 issues); #2659 sat at open-list position 110, outside the window the filer
could see. A filer that forgets its own marker files a duplicate work item every time the open
board grows past the window — reviewers then track one objective in two issues, the dedupe
cleanup becomes host-agent housekeeping, and the bot's issue state stops being evidence.

## What Changes

- `open_issue` resolves the marker through GitHub ISSUE SEARCH instead of the truncated
  listing: `gh api search/issues -f q='repo:"<slug>" "registry-sync-changes: <utc>" in:body
  state:open'`. Search scores the marker string against the WHOLE open board, so a
  marker-bearing issue is found no matter how large the board grows (validated live:
  `total_count=1`, hit #2659, exactly the case the 100-window missed).
- The hit path keeps its existing semantics: the open issue is body-updated over REST PATCH
  (the #2673 transport rule, read-back proven) and re-labelled through the REST labels
  endpoint when the label is missing (#724). Only when search returns NOTHING is a new issue
  created (#704's create path unchanged).
- The create path now always scopes the repo explicitly (`--repo <slug>`) instead of relying
  on gh's inferred checkout repo, so the search, the update and the create all name the same
  repository.

## Impact

- Affected specs: `registry-change-issue` (ADDED requirement: marker dedupe resolves through
  issue search, never a 100-window listing)
- Affected code: `scripts/registry_change_issue.py` (`open_issue`), `tests/test_registry_change_issue.py`
- Affected docs: `agent-wiki/2026-11-16-registry-change-search-dedupe-2847.md`,
  `docs/changes.d/2026-11-16-registry-change-search-dedupe-2847.md`
