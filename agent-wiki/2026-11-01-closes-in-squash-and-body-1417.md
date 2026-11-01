# The unit job checks the squash text and the PR body for the same adjacent close (issue #1417)

Issue: [#1417](https://github.com/asimov-agent/llgenie/issues/1417). The body half of this gate
landed for [#1329](https://github.com/asimov-agent/llgenie/issues/1329).

## What was verified

On main `3c12b4de`, `make ci-unit` already called `make check-pr-closing`, and the unit job in
`.github/workflows/pipeline.yml` ran that target with no `PR_BODY`. The guard job and `scope.yml`
wrote the body to a file and passed only the branch name. `scripts/check_pr_closing.py` did not
read commit messages. `gh api repos/asimov-agent/llgenie` returned
`squash_merge_commit_message=COMMIT_MESSAGES` and `squash_merge_commit_title=COMMIT_OR_PR_TITLE`.

## Key decisions

- The stand-in for the squash body is the joined non-merge commit messages in `PR_BASE..HEAD`,
  the same range `scripts/check_pr_authors.py` reads.
- A claim is an `Issue: #N` line, or a commit subject or pull-request title that ends with `(#N)`.
  Each claim must be an adjacent close in that joined text. When the body is supplied, the two
  adjacent-close sets match. A prose `#N` is not a claim, so a Not covered remainder stays open.
- A change that claims nothing and closes nothing passes. The `agent/*` body rules stay.
- The branch name is `PR_BRANCH`. `PR_HEAD` stays the git revision the author gate reads.
- `check-pr-closing` stays deferred in `scripts/issue_bot_gates.py`. The body still does not exist
  before the pull request event.

## Status

The unit job, the guard step and the scope step pass the body file, the base, the branch and the
title into the gate.
