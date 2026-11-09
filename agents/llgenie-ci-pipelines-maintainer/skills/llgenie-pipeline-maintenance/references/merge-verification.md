# Verifying a merge actually landed

## A squash-merged PR's feature sha is NOT an ancestor of the target branch

The repo squash-merges. The pushed feature head is re-created as a brand-new commit on `main`, so

```
git merge-base --is-ancestor <feature-sha> upstream/main   # returns NO — and that is CORRECT
```

even though the change landed minutes ago. **Never conclude "not merged" from an ancestry test on the
feature sha.** Confirm the merge by, in this order:

1. The PR's own `state`: `gh pr view <n> --json state,mergeCommit,mergeStateStatus` → `"MERGED"` means it
   already landed (by the repo's auto-merge or the owner), whether or not your own `--auto` arm fired.
2. The squash commit on `main`: `git log --oneline -3 upstream/main` shows the squash subject
   `<PR title> (#<n>)` at a NEW sha. That new sha is the one to reference, not the old feature head.
3. Re-run the gate at the new `main` head — the verifiable criterion is the gate's own exit code at the
   squash commit, not the feature sha.

## A squash-merge tip has ZERO workflow runs at its own `head_sha` — "is the merge tip green" is not a `head_sha` query

A squash merge creates a brand-new commit on the default branch that never itself triggered a
`pull_request`/`push` run, so `gh api repos/<o>/<r>/actions/runs?head_sha=<merge-sha>` returns an
**empty list** — measured: `head_sha=24b97d50` gave `0` runs at a merge tip that IS verified green.
Do not read that empty list as "the merge is unverified/red". The merge tip's greenness is proven
by, in this order: (1) the PR's own **pre-merge matrix at its pre-merge head** (the run that was green
before the squash — e.g. the full CI matrix with all jobs), (2) the PR's **bot-verdict approve**
comment (head = the pre-merge head, conclusion approve), and (3) the **MERGED-verification record** on
the PR/issue thread (the planner or lane comment stating the merge sha and the main run that
succeeded). A dispatch that frames "the merge tip is NOT verified green" by citing ci-verdict wrapper
runs is answered with THESE three, never with a runs-at-merge-sha query — and remember the wrapper's
own `head_sha` is the default branch, not the run it consumed (see SKILL.md ci-verdict rule).

## Arming is not the same as merging

`gh pr merge <n> --squash --auto` exits 0 whether or not it armed anything. If the PR is already
`state:"MERGED"`, the arm is moot — do not re-arm, do not force; verify and report. (The full
read-back-the-arm rule is a standing fleet rule; this file only covers the squash-ancestry trap that
makes a correctly-landed change look unmerged.)
