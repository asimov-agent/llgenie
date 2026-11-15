# Tasks — registry-review-rest-body-edit (#2691)

## 1. Transport fix
- [x] 1.1 Add `_REFUSED`, `_gh_api`, `repo_slug`, `_edit_body` to `scripts/registry_review.py` (mirror the proven `registry_change_issue.py` seam: REST PATCH + exact-body read-back + refused-403 report) and call it from `publish`'s update branch instead of `gh issue edit --body`

## 2. Proof + refusal behaviour
- [x] 2.1 Read-back compares the exact body written; a mismatch raises SystemExit naming the issue
- [x] 2.2 A 403-class refusal prints issue + endpoint + capability on stderr and `publish` returns `update refused for #N`

## 3. Tests
- [x] 3.1 Fake `gh` in `tests/test_registry_review.py` raises on any `issue edit` transport call
- [x] 3.2 Update test asserts PATCH to the issue endpoint, the read-back call, and stored-body equality
- [x] 3.3 New test: a PATCH that exits 0 but never stores fails the step naming the issue
- [x] 3.4 New test: a refused 403 write reports issue + endpoint + capability, returns `update refused for #N`, and never reaches GraphQL

## 4. Sync + record
- [x] 4.1 `agent-wiki/` entry + `docs/changes.d/` row + CHANGES.md index row naming issue #2691 and the PR (and #2673 as the origin)

## 5. Verification
- [x] 5.1 `make openspec-validate NAME=registry-review-rest-body-edit` exits 0
- [ ] 5.2 `make test-unit` exits 0 at head (the whole unit suite)
