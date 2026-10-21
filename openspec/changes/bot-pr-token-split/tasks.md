# Tasks — bot-pr-token-split (issue #430)

- [x] 1. OpenSpec change: `proposal.md`, `specs/bot-pr-token-split/spec.md`, this checklist
- [x] 2. `scripts/issue_implementer.py`: `_gh(…, token=)` (per-call env only), `pr_token()`, and `open_pr()` posting the claim comment first, the PR with the PAT, the marker with the job token
- [x] 3. `.github/workflows/issue-bot.yml`: the PR step carries `GH_TOKEN: ${{ github.token }}` and `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}`
- [x] 4. `tests/test_bot_pr_tokens.py`: a real fake `gh` recording the token it received (order, per-write token, denied-comment-stops-before-PR, PAT fallback, the workflow's env); the two `open_pr` call sites in `tests/test_issue_implementer.py` updated
- [x] 5. `README.md` + `agent-wiki/2026-10-21-bot-pr-token-split.md` record which write uses which token
- [x] 6. Verified: `make test-unit` green, `make check-docs`, `make lint`, `make check-wiring`, `make openspec-validate NAME=bot-pr-token-split` green, plus the live proof that a per-call token reaches `gh` (ambient token answers, a bogus per-call token is refused 401)
