# Fork PRs: auto-merge and rebase — depth notes

Companion to the two sections in SKILL.md. Each failure below presents as "CI green, PR still
open", and each is a separate gate.

## Gate 1 — a `pull_request` job from a fork gets no secrets

GitHub does not pass repository secrets to a `pull_request` run whose head repo is a fork. A merge
step that needs `secrets.BUMP_TOKEN`/`GH_TOKEN` runs with an EMPTY string and cannot merge or
approve. The run can still look green because the step falls through or `|| true` swallows it — the
original bug class this repo hit.

- Trigger the merge on `workflow_run` (`workflow_run: workflows: [CI] types: [completed]`); it runs
  in the base repo with base-repo secrets.
- The payload has no PR number; resolve one from the completed run's head SHA/branch.
- Check the resolved PR's `head.repo.full_name` is the expected fork before merging.

## Gate 2 — a trusted author cannot self-approve

When the token's account IS the PR author, `gh pr review --approve` fails; GitHub refuses
self-approval. A green PR then sits `BLOCKED` / `REVIEW_REQUIRED` forever.

- For a trusted author — repo owner, a collaborator with write access, or the bot — skip approval
  and merge with `gh pr merge --squash --admin --match-head-commit <sha>`.
- Gate on the author's permission:
  `gh api repos/$OWNER/$REPO/collaborators/$AUTHOR/permission` returning
  `admin`/`maintain`/`write`, or author == repo owner, or author == bot login.
- Everything else defers: a stranger's green PR, a conflict, a stale branch, a draft, and the
  `do-not-merge` label.
- A 403 on `--admin` means the token lacks admin; print the reason and fail loudly — a silent
  degradation to "deferred, exit 0" reproduces the invisible green-and-never-merges state.

## Gate 3 — the run→PR lookup 404s for fork heads

Measured failing step:

```
gh api repos/<o>/<r>/actions/runs/<run_id>/pull_requests   → gh: Not Found (HTTP 404)
```

Under `set -euo pipefail` the 404 exits the step before the fallback line runs. Even without
`set -e`, the common fallback is wrong: `gh pr list --head <owner>:<branch>` matches a SAME-REPO
branch only and returns `[]` for a fork head. The working lookup is the search qualifier:

```bash
number=$(gh api "repos/$REPO/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number // empty' || true)
if [ -z "$number" ]; then
  number=$(gh pr list --repo "$REPO" --search "head:$HEAD_BRANCH" --state open \
    --json number,headRepositoryOwner \
    --jq ".[] | select(.headRepositoryOwner.login==\"$HEAD_OWNER\") | .number" | head -1)
fi
```

- Keep the `|| true` on the endpoint — a 404 is "no answer", not a failure.
- Filter the search result by head owner; a same-named base branch is a different PR.
- Lock the workflow text in a test (`assert "|| true" in step`, `assert '--search "head:$HEAD_BRANCH"'
  in step`, and assert the same-repo `--head` qualifier is NOT there) — the fix is in YAML and only a
text assertion keeps it.
- `workflow_run` does not re-fire for an already-completed run: after the fix lands, the affected PR
  needs one NEW CI run (rebase or empty commit) before the corrected lookup sees it.

## The rebase sweep's comment hold

`scripts/rebase_bot_sweep.py` leaves a PR alone when it believes another bot owns it. If the claim
reader treats ANY comment as a claim, an ordinary status comment parks the PR; the sweep prints
`pass-over: #N ... no open PR needs rebasing` while the branch is behind base.

- Hold only on the explicit claim marker the bot itself posts. A plain comment is not a claim.
- Rebase states are `BEHIND` and `DIRTY`. `BLOCKED` is a review state, not a rebase trigger by
  itself; a PR that is both blocked and behind still gets rebased.
- A fixture that "posts a claim" must use a word the regex accepts — a non-matching word exercises
  the no-claim path and locks nothing.
- Confirm a branch is behind before arguing: `gh api repos/<o>/<r>/compare/<base>...<branch> --jq .status`.

## Diagnosis order

1. `gh pr view <n> --json state,mergeStateStatus,mergeable,headRefName,author` — a green PR with
   `BLOCKED` is the review gate, not CI.
2. Confirm the workflow file is on the base repo's default branch. A fix living only in an open PR
   merges nothing.
3. If the merge run failed, read the run's failed step (`gh run view <id> --log-failed`) and look for
   the 404 / empty-token line before touching the logic.
4. After a merge, re-read the PR: `state: MERGED`, base branch SHA moved.
