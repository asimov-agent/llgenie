# Tasks

## The shared paginated scan

- [x] 1.1 `bot_claims.paginate_open_issues` walks `gh api repos/{owner}/{repo}/issues?state=open&per_page=100&page=N` through a caller `gh_call` seam until a short page, filters out pull requests, and normalises `createdAt` (issue #2849).
- [x] 1.2 `issue_dedup.candidates` routes its open scan through the helper (its own `_gh`/gh-path seam).
- [x] 1.3 `issue_cleaner.open_issues` routes its open scan through the helper (`_gh`).

## Proving coverage past the old 200-boundary

- [x] 2.1 `test_a_pair_straddling_the_old_200_boundary_is_still_found` (dedup): 205 open issues, oldest similar member at position 201+ — the pair is still picked with the older as canonical. RED on `--limit 200` (oldest missed), GREEN on the paginated scan.
- [x] 2.2 `test_a_close_behind_open_list_position_200_is_still_seen` (cleaner): 205 open issues, implemented issue at position 201+ — the merged-PR stale-open close fires. RED on `--limit 200`, GREEN on the paginated scan.
- [x] 2.3 Existing `test_issue_dedup.py` / `test_issue_cleaner.py` cases pass unchanged (stubs now answer the paginated `gh api` call).

## Gates + docs

- [x] 3.1 `make test-unit` runs 3905 passed / 1 failed — the lone failure is the PRE-EXISTING, environmental
  `tests/test_repo_slug.py::test_the_documented_invocations_carry_the_slug` (this container's `make -n`
  prints an "Entering directory '/repo'" cwd banner the test asserts absent; it fails identically on a clean
  tree and is unreachable from this change). Both affected modules and both new straddle tests pass.
- [x] 3.2 `agent-wiki/2026-11-16-paginate-open-issue-scan.md` references the issue and the PR, and `CHANGES.md` gains its row (check-docs).
- [x] 3.3 `make openspec-validate NAME=paginate-open-issue-scan` passes (CI, docker-backed).
