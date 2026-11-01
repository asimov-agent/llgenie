# closes-in-squash-and-body — proposal

Issue: [#1417](https://github.com/asimov-agent/llgenie/issues/1417)

## Why

`make check-pr-closing` (issue #1329) refuses an `agent/*` pull request whose body has no adjacent
`closes|fixes|resolves #N`. The linux unit job runs `make ci-unit` without the body, so that half
never sees the pull request. The script never reads commit messages. This repository squash-merges
with `squash_merge_commit_message=COMMIT_MESSAGES` (measured on the repo settings, main `3c12b4de`).
The commit that lands is the joined branch commit messages. GitHub auto-close reads the pull request
body. Those two texts can disagree, and the unit job still goes green.

## What changes

- `scripts/check_pr_closing.py` joins the non-merge commits in `PR_BASE..HEAD` and treats that text
  as the squash body. A claim is an `Issue: #N` line, or a commit subject or pull-request title that
  ends with `(#N)`. Each claim must be an adjacent close in the joined text. When the body file is
  supplied, the body's adjacent-close set and the commit text's adjacent-close set are the same set.
  A change that claims nothing and closes nothing passes. A prose `#N` is not a claim.
- The existing `agent/*` body rules stay. `closes **#N**` stays a miss.
- The unit job, the guard step and the scope step pass the body file, `PR_BASE`, `PR_BRANCH` and
  `PR_TITLE` through the environment. `PR_HEAD` stays the git revision the author gate reads.
- `check-pr-closing` stays a deferred issue-bot gate. The reason now says the commit half is readable
  from git and the body half still waits for the pull request event.
