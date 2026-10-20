# Tasks

- [x] 1. `scripts/secret_scan.py`: compute the committable set (`git ls-files -c -o --exclude-standard`), export it, run the pinned gitleaks image + the repository config against the export; `--list` prints the set
- [x] 2. `Makefile`: `_secret-scan` calls the script; `secret-scan` separates a finding (exit 1) from a scan that could not run (any other non-zero) instead of calling every failure "a credential is present"
- [x] 3. `tests/test_secret_scan.py`: the committable set excludes an ignored artifact and includes tracked + fresh untracked files; the real tree holds no ignored path; the wrapper's two messages
- [x] 4. `README.md` documents what the scan reads; `agent-wiki/2026-10-20-secret-scan-committable.md` records the work with issue #382 and the PR
- [x] 5. Measured before/after in a real checkout: the same planted value in a gitignored path is found by `gitleaks dir` (rc=1) and NOT by `make secret-scan` (rc=0), while a planted value in a tracked and in a fresh untracked file still fails the scan
- [x] 6. Verification: `make check-wiring`, `make check-docs`, `make check-workflows`, `make check-secret-output`, `make lint`, `make openspec-validate NAME=secret-scan-committable`, `make test-unit`
