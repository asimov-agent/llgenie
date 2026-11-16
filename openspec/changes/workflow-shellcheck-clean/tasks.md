# Tasks: workflow-shellcheck-clean

- [x] Fix SC2129 grouped-redirect findings in the eight bot-summary steps (architecture-bot, code-review-bot, fix-bot, issue-bot, issue-dedupe, rebase-bot, review-verdict, run-failure-reactor)
- [x] Fix engine-bump.yml findings: quote `${ID}`/`${ENGINE}` expansions (SC2086), move `${{ github.repository }}` out of the single-quoted printf format (SC2016)
- [x] Fix security-scan.yml SC2209 ENFORCE indirection, semgrep-rules-refresh.yml SC2028 echo->printf, stale-branch-cleanup.yml SC2046 unquoted command substitution (+ issue-dedupe SC2143)
- [x] Keep `concurrency.queue: max` (engine-build.yml, issue #2294) and document the actionlint exception as a single narrow `-ignore` regex in the Makefile gate block
- [x] Add digest-pinned `ACTIONLINT_IMAGE` + `check-workflows-shellcheck` target; chain it into `check-workflows`; declare `.PHONY`
- [x] Verify: pinned actionlint exits 0 over `.github/workflows/` with only the queue-key ignore; the no-ignore sweep reports exactly 1 residual (engine-build.yml:94:3)
- [x] Test-pin the wiring in `tests/test_workflows_valid.py` (chain, .PHONY, digest pin, exactly-one-ignore, queue key survives) and document the chained step in README + ARCHITECTURE; module suites `test_workflows_valid.py` + `test_changes_index.py` + `test_check_docs.py` rc=0 (72 passed)
- [x] Update issue #329 body to the measured live set (six-section shape, ticked ACs with proven strings) and mirror acceptance into PR body + commit text
- [x] Docs: agent-wiki entry + changes.d fragment naming #329 (note of the fragment's own name)
- [x] Gate: `make openspec-validate NAME=workflow-shellcheck-clean` rc=0, `make check-workflows` rc=0, full `make test-unit` green against the pushed head, and `make lane-preflight` prints `preflight: OK` on the pushed tree (CI run ids recorded on issue #329)
