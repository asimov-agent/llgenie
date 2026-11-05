# Commit identity, force-push and CI registration

## `check-pr-authors` — the commit-identity gate

The repo admits only an allowlisted author identity for every commit in the PR
range: **`Asimov Agent <support@docondee.com>`**. The GitHub noreply address
(`asimov-agent@users.noreply.github.com`) is NOT allowlisted — a PR whose only
red is `guard` / `check-pr-authors` almost always means the commit was made with
the default noreply identity, not that anything in the diff is wrong.

Read the gate's own allowlist instead of guessing:

```sh
python3 scripts/check_pr_authors.py check --base <base-sha> --head HEAD
# [check-pr-authors] OK — every commit in the range is authored by an allowed identity
```

## Fixing the author without touching content

Re-author every offending commit with `--reset-author` and both committer env
vars (the gate checks author; CI provenance reads committer, so set both):

```sh
git rebase --exec 'GIT_COMMITTER_NAME="Asimov Agent" GIT_COMMITTER_EMAIL="support@docondee.com" \
  git -c user.name="Asimov Agent" -c user.email="support@docondee.com" commit --amend --reset-author --no-edit' <base>
# single-commit branch, simpler:
GIT_COMMITTER_NAME="Asimov Agent" GIT_COMMITTER_EMAIL="support@docondee.com" \
  git -c user.name="Asimov Agent" -c user.email="support@docondee.com" commit --amend --reset-author --no-edit
```

- `--reset-author` **rewrites the sha** even though the tree is byte-identical.
  Say "metadata-only rewrite, content unchanged" in the PR comment so a reviewer
  diffing the old and new head does not think the patch changed.
- Set `user.email` on the repo/worktree too, or every later commit reintroduces
  the defect.

## Lease force-push after a rewrite

A rewrite needs a force-push, and the lease must be pinned to the sha the remote
holds *right now* — read it, do not reuse a sha from earlier in the session:

```sh
remote=$(git ls-remote origin refs/heads/<branch> | cut -f1)
git push --force-with-lease=refs/heads/<branch>:$remote origin <branch>
```

Verify the PR actually moved before writing any verdict:

```sh
gh api repos/<owner>/<repo>/pulls/<n> --jq '{head:.head.sha[0:12],mergeable,state}'
```

## New heads do not get CI runs instantly

After PR creation or a force-push, `actions/runs?head_sha=<sha>` can return `[]`
for 60–120 s. Poll `gh run list --branch <branch> --limit 3` instead of
concluding "no CI"; a run list keyed on the branch surfaces them as soon as they
register. Then confirm each run's jobs (`/actions/runs/<id>/jobs`) rather than
reading the run's `conclusion` field, which stays empty until the last job ends.

## Gates to check before declaring a head done

- `make check-pr-authors PR_BASE=$(git rev-parse origin/main)` → rc 0.
- `gh pr view <n> --json mergeable` → `MERGEABLE`; a `CONFLICTING` result is the
  only trigger for a rebase (see the standing rule: never rebase to chase main).
