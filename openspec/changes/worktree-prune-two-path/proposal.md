# worktree-prune-two-path — proposal

Issue: [#2262](https://github.com/asimov-agent/llgenie/issues/2262)

## Why

`make worktree-prune` prunes only a branch that is the `headRefName` of a MERGED PR whose
`mergeCommit.oid` is an ancestor of the base. Measured at issue time the host leaked **157
worktrees / 9.4 GiB under `llgenie-wt/`**, `/tmp` at 16% free. Two classes of dead work fell
through the PR-only rule: a branch whose PR merged under another name (a `rb-*`/`sw-*`/`rev-*`
rebase/verification scratch), and any branch whose head is already an ancestor of `origin/main`
but that names no PR. The owner (2026-11-08) set the rule: prune worktrees *"that has no open
issue nor open PR yet"*, and make it a tick step.

## What Changes

- **`scripts/worktree_prune.py`** gains the owner's two-path eligibility: a branch is prunable when
  it is the `headRefName` of a MERGED PR whose `mergeCommit.oid` is on the base **OR** its own head
  is an ancestor of the base (ancestry-merged), and the three guards are conjunctive for any delete:
  no OPEN PR names it, no OPEN issue its `issue-NNN`/`<NNNN>-` token names, and it is merged by
  ancestry or PR commit. A head **ahead** of `origin/main` is never deleted whatever the PR/issue
  state. The base's own local branch is never a candidate. After a local prune, the matching
  `origin/` remote branch is deleted too, gated on the same no-open-PR test.
- **`issue_token()` / `issue_state()`** implement the no-open-issue gate: a closed or absent issue
  is "not open". **`delete_remote_branch()`** no-ops on a missing remote ref and records (never
  swallows) a failed push.
- **The orchestrator tick's STEP 10** (already landed with the #2262 mandate in #2272) has its /tmp
  step tightened to call the canonical `make reclaim-tmp-worktrees DRY=0` (landed by #2141) instead
  of hand-rolling the ancestry check; FORCE stays the #794-guarded owner exception, never a pass
  step.
- **`tests/test_worktree_prune.py`** gains the issue's cases over `_gh_stub` (now answering
  `issue view` from `issues.json`).

## Acceptance

- The pruning tests are green (`31 passed`).
- `make check-docs`, `make changes-index`, `make check-wiring`, `make lane-preflight` all exit 0.
