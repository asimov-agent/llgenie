# Commit identity, force-push and CI registration

## `check-pr-authors` — the commit-identity gate

The repo admits only allowlisted author identities for every commit in the PR
range. There is **more than one** allowlisted identity (e.g. both
`Asimov Agent <support@docondee.com>` and `Andy Holst <andy.holst@protonmail.com>`
have passed); the default local identity (`<lane>@llgenie.local`) and the GitHub
noreply address (`asimov-agent@users.noreply.github.com`) are NOT allowlisted. A
PR whose only red is `guard` / `check-pr-authors` almost always means the commit
was made with a non-allowlisted identity, not that anything in the diff is wrong.
**Read the current allowlist from the gate script instead of assuming a single
identity** — the set changes over time.

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
git push --force-with-lease=refs/heads/<branch>:$remote origin <local>:<branch>
```

- **Push an explicit `src:dst` refspec** (`origin <local>:<branch>`), never a bare
  `origin <local>`. A bare local-branch name pushes to a remote branch of that SAME name — when
  your local branch name differs from the PR's branch, it silently CREATES a stray remote branch
  and leaves the PR's branch untouched (the PR head does not move, and you get a phantom branch).
  Delete the stray (`git push origin --delete <stray>`) and re-push with the colon.
- **Never pass two sources for the same destination.** `git push origin <branch> <sha>:<branch>`
  aborts with `dst ref refs/heads/<branch> receives from more than one src` and pushes NOTHING.
  Pick one form: `git push origin HEAD:<branch>` (simplest after committing) or
  `git push origin <sha>:<branch>`.  Instead, `git ls-remote origin <branch>` to confirm the remote now points to the sha you intended.

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

## Committing onto ANOTHER lane's PR branch (a fixture/pointer commit)

When a dispatch says the change "belongs in an existing PR's lane, one vehicle",
you push a commit onto a branch another lane owns. Two gates then apply to *your*
commit on top of everything the branch already carries:

- **`check-pr-authors`** — same rule as above: author the commit with an
  allowlisted identity (`--reset-author` with `user.name`/`user.email` set), or the
  whole PR reds on a commit that is otherwise fine.
- **`check-pr-closing`** — the squash-text close set is the union of the PR body's
  `closes #N` and every commit message's closing keywords. A commit message that
  adds `closes #<other>` for an issue the PR body does not close reds the gate,
  even when the body itself is correct. For a *reference* to another issue (not a
  close), write it **without a closing keyword** — `(issue #N)` or `refs #N`, never
  `closes #N` / `fixes #N`.

Push it as a plain fast-forward when the current wire head is the commit's parent
(no force needed); force-with-lease only if you rewrote your own commit. After the
push, read the guard job's per-step list (see `gate-red-triage.md`) to confirm
`check-pr-authors` and `check-pr-closing` both conclude `success` at the new head —
the run's overall `failure` says nothing about *which* step reds.

## Gates to check before declaring a head done

- `make check-pr-authors PR_BASE=$(git rev-parse origin/main)` → rc 0.
- `gh pr view <n> --json mergeable` → `MERGEABLE`; a `CONFLICTING` result is the
  only trigger for a rebase (see the standing rule: never rebase to chase main).
