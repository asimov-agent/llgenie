# Tasks — registry-review-publish-rest

- [x] 1. `scripts/registry_review.py::publish`: replace the `gh issue edit --body` GraphQL call with the REST `gh api -X PATCH repos/<slug>/issues/<n> -f body=...` seam; add `repo_slug`/`_gh_api` helpers and a `_REFUSED` token tuple (mirroring `registry_change_issue.py`).
- [x] 2. Read the body back over the same REST endpoint and fail the step (naming the issue) when the stored body != the body written (the #819 silent-drop red).
- [x] 3. On a refused write (`HTTP 403` / `not accessible by personal access token`) print one loud line naming the issue + endpoint + capability and return without raising (the #775 credential-fact rule).
- [x] 4. `tests/test_registry_review.py`: update the duplicate-publish test to assert the REST PATCH + read-back; add the silent-drop failure test and the refused-write survival test, each with `# Given / # When / # Then` markers and wired into the aggregated unit suite.
- [x] 5. OpenSpec change files (proposal/specs/tasks + `.openspec.yaml`) present; `tasks.md` all ticked; the sibling `registry_change_issue.py` untouched.
- [x] 6. Docs: `agent-wiki/2026-11-15-registry-review-publish-rest.md` naming #2691 and the PR + `CHANGES.md` row.
- [x] 7. Gates green on the final tree: `make test-unit` (run id: full-suite 3798 passed / 2 environmental failures on `/repo` path + JEV, neither touching registry_review; `tests/test_registry_review.py` 15 passed), `make lint`, `make check-wiring`, `make check-docs`, `make openspec-tasks-check`, and `grep -n '"issue", "edit"' scripts/registry_review.py` exits 1.
