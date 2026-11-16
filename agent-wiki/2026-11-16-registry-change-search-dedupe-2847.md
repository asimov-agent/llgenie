# 2026-11-16 — the registry-change filer dedupes by issue SEARCH, not a 100-issue window (issue #2847)

## What was verified

- Measured the defect on the live board: the weekly `registry-sync` lane re-filed the
  2026-11-15T08:29:53Z store review as #2847 although #2659 already carried its exact dedupe
  marker (`<!-- registry-sync-changes: 2026-11-15T08:29:53Z -->`). The open window spanned
  #2845..#2738 (100 issues, newest-first); #2659 sat at open-list position 110 — past the
  `--limit 100` window `scripts/registry_change_issue.py::open_issue` scanned.
- Validated the replacement live: `gh api search/issues -f
  q='repo:asimov-agent/llgenie "registry-sync-changes: 2026-11-15T08:29:53Z" in:body state:open'`
  -> `total_count=1`, item #2659 — the exact case the window missed, found by whole-board search.
- New unit test `test_a_marker_issue_ranked_past_the_open_window_is_still_updated` drives
  `open_issue` against a 101-issue open board whose marker issue sits last: it returns
  `updated #2659`, issues one REST body PATCH and one label POST, and never calls `issue create`.
  `tests/test_registry_change_issue.py` passes 11/11; the emitted `gh` search argv matches the
  validated query byte-for-byte.

## Key decisions

- Dedupe memory is now a body SEARCH, not a position in a page of 100: `open_issue` resolves the
  marker with `search/issues? q=... in:body state:open`, which scores the marker across the whole
  open board. The 100-window listing is gone.
- The hit path keeps its #2673/#724 semantics — REST body PATCH with a read-back verdict, and a
  REST label re-queue when `agent:implement` is missing — and the create path now always scopes
  `--repo <slug>` so search, update and create all target the same repository.
- The same-class, different-mechanism window in the pairwise dedupe bots (`issue_dedup.py`,
  `issue_cleaner.py` cap at 200) is NOT in scope: filed as its own linked issue #2849.

## Current status

The change (script + tests + docs) is implemented and uncommitted in this worktree for the job to
commit. `make test-unit` green on this head. The OpenSpec change
`openspec/changes/registry-change-search-dedupe/` was hand-written to mirror the repo's reference
change structure because this agent container has no Docker daemon (the `make openspec-*` path is
containerised) — the `ci-openspec` job in the real pipeline validates it. `make lane-preflight`
prints `preflight: OK` (see the PR body).
