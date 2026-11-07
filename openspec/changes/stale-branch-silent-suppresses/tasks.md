# Tasks

- [x] Reproduce: `gh api --paginate --silent <branches>` rc=0 stdout=0 bytes vs 15249 without, at main 6940f9e7
- [x] Drop `--silent` from `_paged_json`; branch-list read returns the populated body
- [x] Add regression test that models real `gh` body-suppression (a `--silent` call prints nothing); it FAILS on the old tree and PASSES on the fix (guard-proven)
- [x] Run the script report-only against the real API: lists would-delete set with evidence, exits 0
- [x] Confirm the safety predicate holds (open-PR / unreachable branches are kept, never deleted)
- [x] `tests/test_stale_branch_cleanup.py` 11 passed; lane-preflight (6 gates) green; change-note trio + openspec scaffold committed
