# Tasks

- [x] 1. `openspec/changes/auto-merge-recheck-stale-head` — proposal + `specs/auto-merge-recheck-stale-head/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before any code
- [x] 2. `scripts/auto_merge.py::recheck` — sweep a PR carrying ANY deferral marker whose current head is green (no red + concluded green run); keep one-comment-per-head dedupe, the `max_prs` cap, the #1386 red rule, and a never-deferred PR untouched
- [x] 3. `tests/test_auto_merge.py` — `test_a_stale_marker_green_head_is_retried_and_merged` (merges, no `--admin`), `test_a_stale_marker_red_head_is_not_retried` (red current head deferred, never approved/merged)
- [x] 4. `agent-wiki/2026-11-07-auto-merge-recheck-stale-head.md` + `docs/changes.d/2026-11-07-...md` + CHANGES.md row
- [x] 5. Verified: `make test-unit` green (92 in test_auto_merge, full file), `make check-docs`, `make changes-index`, `make lint`, `make openspec-validate-all` all exit 0; the green-head test is mutation-proved (fails on the pre-fix skip, passes on the fix)
