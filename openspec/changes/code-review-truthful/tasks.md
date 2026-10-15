# Tasks

- [x] 1. File the issue with measured evidence (issue #307): the commented `secrets.X` finding reproduced with `make code-review-scan`, and the tokenless scan step's `no findings` vs the filer's 3.
- [x] 2. Strip full-line comments in `check_secrets_not_defined` so a commented `secrets.X` is not a finding.
- [x] 3. Give the workflow's `scan` step the same `GH_TOKEN` as the filer step.
- [x] 4. Add the tests (commented `secrets.X` no finding; real `secrets.X` still a finding; the scan step carries `GH_TOKEN`).
- [x] 5. Prove the tests fail on the pre-fix tree and pass after (rule 6c): `2 failed, 1 passed` on `git show origin/main:…`, 23 passed after.
- [x] 6. Update `README.md` if the change alters a user-facing surface, and add an `agent-wiki/` entry citing #307. (No user-facing make target changed; the work record cites #307/#308.)
- [x] 7. Verified: `make lint`, `make openspec-validate NAME=code-review-truthful`, `make check-wiring`, `make check-docs` all green, and `tests/test_code_review.py` 23 passed in the test image.
