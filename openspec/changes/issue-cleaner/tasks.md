# Tasks

- [x] 1. `scripts/issue_cleaner.py`: `implemented_issue()` derives the implemented issue from `closingIssuesReferences`, the merge commit's `Issue: #<n>` and the title's trailing `(#<n>)` — in that strength order — and yields `None` when the body closed it or names none
- [x] 2. `not_covered()` parses the PR's `Not covered` section up to the next heading, so a remainder list cannot swallow a later section
- [x] 3. `decide()` returns a `close` finding for an implemented issue that is still open, a `remainder` finding when the PR disclaimed it, and `None` when the issue is already closed
- [x] 4. `main()`: `--dry` prints every finding and mutates nothing; `--json` emits them; the default run posts the evidence comment and closes as completed, announcing itself first through the shared claim marker
- [x] 5. `scripts/bot_claims.py` gains the `clean` work verb (`CLAIM_RE` + the writer's assertion) and the `CLEANER` name, so the bot joins the one claim protocol (#279) instead of inventing a second
- [x] 6. `tests/test_issue_cleaner.py`: pure-logic cases (section parsing, signal priority, remainder vs close) plus end-to-end runs driving the real module with `gh` stubbed on `PATH` — **14 passed** in `llgenie/test:latest`; `tests/test_bot_claims.py` still **14 passed**
- [x] 7. Falsified: with the `closingIssuesReferences` guard and the `Not covered` parse neutered, the same suite gives **5 failed, 9 passed**; restored, **14 passed**
- [x] 8. `make issue-cleaner-scan` and `make issue-cleaner-apply` resolve to `python3 scripts/issue_cleaner.py --repo ... [--dry]` via `make -n`; both are in `.PHONY`
- [x] 9. `tests/test_issue_cleaner.py` is in the `test-unit` list, so `make test-unit` and `make ci-unit` run it; the scan stays out of the offline `ci-unit` path
- [x] 10. Ran it for real against the repo: it reported stale-open **#256** (implemented by merged #344, no closing reference) and 5 tracked remainders (#339-#343), which were left open
- [x] 11. Closed #256 with an evidence comment naming #344, its merge commit and #339 as the tracked remainder
- [x] 12. README names the two targets; `agent-wiki/2026-10-16-issue-cleaner.md` records the work with `#325`, `#256`, `#344` and `#339`
- [x] 13. `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-dispatch-forms` and `make openspec-validate NAME=issue-cleaner` exit 0
