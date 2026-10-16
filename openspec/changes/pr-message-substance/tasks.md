# Tasks

- [x] 1. Write the proposal + spec for the PR/commit message-substance mandate (issue #313).
- [x] 2. `AGENTS.md`: the mandate section — a commit/PR message carries the issue, the fix, the
      benefit, plus the technical extension; never empty or placeholder.
- [x] 3. `scripts/check_pr_hygiene.py` (`check` / `report`) + `make check-pr-hygiene` /
      `make pr-hygiene-report`, wired into `ci-unit`.
- [x] 4. The producers emit a real body: `engine-bump.yml`, `issue-bot.yml`, `registry-sync.yml`
      commit a subject + a three-part body.
- [x] 5. `tests/test_pr_hygiene.py`: the fixture violations (bodiless commit, placeholder subject,
      non-conventional subject, missing/empty PR body), the accepted shapes, the Python argv form,
      the missing AGENTS.md mandate, the exit-code contract and the real tree passing — wired into
      `test-unit`.
- [x] 6. README line + section for the two targets, and the `agent-wiki/` work record naming `#313`.
- [x] 7. Verify: `make check-pr-hygiene`, `make lint`, `make check-docs`, `make check-wiring`,
      `make check-dispatch-forms`, `make check-secret-output`,
      `openspec-validate NAME=pr-message-substance`, the touched suites in `llgenie/test:latest`, and
      CI green on the PR.
