# The merge runs where the secrets are: `auto-merge` is a `workflow_run` workflow

- Issue: [#493](https://github.com/asimov-agent/llgenie/issues/493)
- Complements: [#491](https://github.com/asimov-agent/llgenie/issues/491) (the review-requirement path)
- OpenSpec change: `auto-merge-workflow-run`
- Branch: `feat/auto-merge-review-approve`

## What was wrong

#481's CI run was green and its `auto-merge` job **succeeded**, yet the PR stayed open. The job log showed
`GH_TOKEN:` empty — `secrets.BUMP_TOKEN` resolved to nothing — because the job lived in `ci.yml`, which runs
on `pull_request`, and **GitHub withholds repository secrets from a `pull_request` run coming from a fork**.
Every agent PR here comes from `andyholst/llgenie`, so every merge job was structurally unable to merge: it
reported success and did nothing.

## What changed

- New `.github/workflows/auto-merge.yml`, `workflow_run: workflows: ["CI"], types: [completed]` — it executes
  in the base repository, where the PAT exists. Guards: `event == 'pull_request'`, `conclusion == 'success'`;
  checks out the **base** branch (write token → trusted code only); resolves the PR from the run
  (`actions/runs/{id}/pull_requests`, then `gh pr list --head owner:branch`); calls `make auto-merge`.
- `ci.yml`'s `auto-merge` job deleted (comment names the new file); the skip-guard's scenario-scoped
  exception in `tests/test_ci_images.py` removed with it.
- `scripts/auto_merge.py`: `_require_token()` exits 2 when no token is set, and `decide()` defers a head from
  a third-party fork (`TRUSTED_HEAD_OWNERS = ("andyholst",)`) — the old job `if:` trust rule, now where the
  decision is made.
- `README.md` describes the workflow_run shape and why it is not a job in `ci.yml`.

## Verified

- `pytest tests/test_auto_merge.py tests/test_ci_images.py` → 53 passed.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=auto-merge-workflow-run` — green.
- `make test-unit` — green (numbers in the PR).

## Notes

- `workflow_run` only starts once the triggering workflow exists on the default branch, so the first
  post-merge `main` run registers it; a fork PR triggers it on its next CI run.
- A same-account PR still needs a human approval (GitHub's self-approval rule); the deferral comment says so.
