## 1. Transport fix

- [x] 1.1 `scripts/registry_change_issue.py`: update branch writes via `gh api -X PATCH repos/<slug>/issues/<n> -f body=...`; no `gh issue edit` call remains

## 2. Proof + refusal reporting

- [x] 2.1 Read-back of the marker from `GET repos/<slug>/issues/<n>` after the PATCH; silent-drop → SystemExit naming the issue
- [x] 2.2 Refused PATCH (403 class) → one loud stderr line naming issue + endpoint + capability; leg survives

## 3. Tests

- [x] 3.1 Update the fake-`gh` (PATCH stores body, `--jq .body` read-back) and pin the update test to `api -X PATCH` with `issue edit` never called
- [x] 3.2 New tests: silent-drop body write fails the step naming the issue; refused body write reports issue+endpoint+capability and survives

## 4. Sync + record

- [x] 4.1 Issue #2673 body/AC mirror the implemented shape; out-of-scope item filed as its own linked issue (registry_review.py GraphQL `--body` edit)
- [x] 4.2 `agent-wiki/` entry naming issue #2673 and the PR

## 5. Verification

- [x] 5.1 `make openspec-validate NAME=registry-sync-change-issue-rest-edit` exits 0
- [x] 5.2 `make test-unit` exits 0 at head (the whole unit suite, not just the module)
