# Tasks: reviewer-finding-dedupe

- [x] 1. `scripts/code_review.py`: add `open_pr_file_map(gh, repo)` using the soft-gh helper (`gh pr list --state open --json number,files --limit 200`); refused read -> loud WARNING + degrade to marker-only filing
- [x] 2. `file_findings()`: fetch the map once per run; before filing, match the finding's `where` files (str or list) against it; on a hit print `already in flight: PR #N (<file>)` and skip filing
- [x] 3. `tests/test_code_review.py`: fake-gh gains a `pr list` branch driven by opts; new tests pin open-PR-touches-file -> not filed + reported, and no-open-PR -> filed (marker dedupe tests unchanged)
- [x] 4. Live proof: `python3 scripts/code_review.py file --repo asimov-agent/llgenie --dry` rc=0 against the live board — live open-PR fetch exercised; the one unfound-marker finding reported `would file`, consistent with the real in-flight map
- [x] 5. Targeted pytest green with the new pins (34/34 incl. 5 new + updated verb-set pin)
- [x] 6. `make openspec-validate NAME=reviewer-finding-dedupe` exits 0
- [x] 7. agent-wiki entry + docs/changes.d row + `make changes-index` + `make check-docs` green
- [x] 8. Commit text mirrors the issue AC block (four ticked mirror lines); `make lane-preflight` prints `preflight: OK`
