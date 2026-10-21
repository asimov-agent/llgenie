# Tasks — auto-merge-green-prs (issue #482)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-green-prs/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: the decision read from one `gh pr view` (OPEN, MERGEABLE, CLEAN, head pinned, no `do-not-merge`), the deferred reasons, and the squash merge with `--match-head-commit`
- [x] 3. `scripts/verify_closure.py` + `make verify-closure PR= REPO=`: a merged PR's closing references, failing and naming an issue that is still OPEN
- [x] 4. `Makefile`: `auto-merge` and `verify-closure` targets, `.PHONY`, `##` help lines
- [x] 5. `.github/workflows/ci.yml`: the `auto-merge` job (`needs:` every PR-relevant job, `always() && !failure() && !cancelled()`, pull_request + non-draft + same-repo + not `main`, owner PAT, `make auto-merge`)
- [x] 6. `AGENTS.md`: rule 7 states the new policy, and the "An APPROVED PR is merged" section is reconciled (the agent never runs `gh pr merge`)
- [x] 7. `tests/test_auto_merge.py` (14 cases): the decision, the deferred reasons, the merge argv, the closure proof, the job's needs/condition/token, the targets' wiring, and AGENTS.md's policy
- [x] 8. `README.md` + `agent-wiki/2026-10-21-auto-merge-green-prs.md` record the policy and how to hold a PR
- [x] 9. Verified: `make test-unit` green (see the PR), `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-pr-hygiene`, `make openspec-validate NAME=auto-merge-green-prs` green
