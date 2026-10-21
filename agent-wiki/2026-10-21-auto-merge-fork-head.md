# The auto-merge job accepts the owner's fork as a PR head

- Issue: [#488](https://github.com/asimov-agent/llgenie/issues/488)
- OpenSpec change: `auto-merge-fork-head`
- Branch: `fix/auto-merge-fork-head`

## What was wrong

`auto-merge` (#483) shipped requiring `head.repo.full_name == github.repository` — a condition copied from
`trending-local-llms`, whose bots push branches **inside** the repo. Here every agent PR is pushed to
`andyholst/llgenie` and opened cross-repository, so the job skipped exactly the PRs it was built for. PR
[#481](https://github.com/asimov-agent/llgenie/pull/481) is the measured case: `head=andyholst/llgenie`,
`mergeable=MERGEABLE`, and its newest run (15:07) predates #483 landing (16:15) — so nothing had even
attempted a merge, and nothing would have while the head condition excluded it.

## What changed

- `.github/workflows/ci.yml` — the head condition accepts the base repo **or**
  `github.event.pull_request.head.repo.owner.login == 'andyholst'` (the account the merge PAT belongs to);
  every other guard is unchanged (non-draft, not `main`, all eight needed jobs `success`,
  `!failure()`/`!cancelled()`).
- `scripts/auto_merge.py` — the same `gh pr view` now also reads `headRepository`; `--delete-branch` is
  passed only when the head repository **is** the base repository, so a fork merge succeeds and the fork
  branch is kept (printed, not failed). No new workflow plumbing.
- `tests/test_auto_merge.py` — the trusted-fork condition (and that there is no wildcard or negation that
  would let any fork through), a fork head merging without `--delete-branch`, and the same-repo head still
  deleting its branch.
- `AGENTS.md`, `README.md`, the change's spec and tasks.

## Verified

- `pytest tests/test_auto_merge.py tests/test_ci_images.py` → 41 passed.
- The `gh pr view` shape the script reads is the real one (`--json …,headRepository`), and the fake `gh` in
  the tests records the argv it was called with, so the "no `--delete-branch` for a fork" claim is asserted
  on the exact command.
- `make lint`, `make check-docs`, `make check-workflows`, `make check-wiring`,
  `make openspec-validate NAME=auto-merge-fork-head` — green.
- `make test-unit` — green (numbers in the PR).

## Notes

- The job still needs a **new** `pull_request` run to fire on an existing PR (a run only starts on a push,
  or a manual re-run). #481's stale `BLOCKED` state clears when a fresh run reports on the new merge commit.
- A fork merge keeps its branch: the base token has no write access to `andyholst/llgenie`, so
  `--delete-branch` would fail after a successful merge. `make worktree-prune` cleans the local side.
