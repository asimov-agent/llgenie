# Tasks — auto-merge-fork-head (issue #488)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-fork-head/spec.md`, this checklist
- [x] 2. `.github/workflows/ci.yml`: the head condition accepts the base repo **or** `head.repo.owner.login == 'andyholst'`, with the reason in the job comment
- [x] 3. `scripts/auto_merge.py`: read `headRepository` from the same `gh pr view`, and pass `--delete-branch` only for a same-repo head (a fork merge keeps its branch and says so)
- [x] 4. `tests/test_auto_merge.py`: the trusted-fork condition (and no wildcard), a fork head merging without `--delete-branch`, the same-repo head still deleting its branch
- [x] 5. `AGENTS.md` + `README.md` + `agent-wiki/2026-10-21-auto-merge-fork-head.md`: the fork rule and that a fork branch is kept
- [x] 6. Verified: `pytest tests/test_auto_merge.py tests/test_ci_images.py` green (41 passed), `make lint`, `make check-docs`, `make check-workflows`, `make check-wiring`, `make openspec-validate NAME=auto-merge-fork-head` green, and `make test-unit` green (numbers in the PR)
