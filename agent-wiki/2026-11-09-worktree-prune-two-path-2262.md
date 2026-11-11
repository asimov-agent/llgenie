# worktree-prune two-path eligibility: PR-merged OR ancestry-merged, held by any open PR/issue (#2262)

`make worktree-prune` pruned only a branch that was the `headRefName` of a **MERGED PR whose
`mergeCommit.oid` was an ancestor of the base**. Two classes of dead work fell through that net
(measured at issue time: 157 worktrees / 9.4 GiB under `llgenie-wt/`, `/tmp` at 16% free):
a squash-merged branch that names no PR at all (its PR merged under another name, or it is a
`rb-*`/`sw-*`/`rev-*` rebase/verification scratch that produced a merged PR under a different
head), and a branch whose head is already an ancestor of `origin/main`. The owner (2026-11-08)
widened the rule: *"run it for worktrees that has no open issue nor open PR yet."*

## The two provable senses of "merged" — conjunctive with the guards

A local branch/worktree is now prunable when **EITHER**:

* its head is the `headRefName` of a MERGED PR whose `mergeCommit.oid` is an ancestor of the base, **OR**
* it names no MERGED PR but its own head IS an ancestor of the base (proven merged by ancestry).

The three guards are conjunctive for **any** deletion (issue #2262):

1. **no OPEN PR** names the branch (`gh pr list --head <branch> --state open` empty),
2. **no OPEN issue** the branch names (`issue-NNN` / `<NNNN>-` token → `gh issue view` closed/absent),
3. merged by ancestry or by PR-merge-commit.

A head **AHEAD** of `origin/main` is never deleted whatever the PR/issue state — the
#794/#791 accident bound. The base's own local branch (`main`) is never a candidate. After a
local prune, the matching `origin/` remote branch is deleted too, gated on the same open-PR
test. `--dry` prints the whole plan and mutates nothing.

`issue_token()` reads `issue-NNN` or a 4-digit `<NNNN>-` run from a branch name;
`issue_state()` treats a closed or absent issue as "not open". `delete_remote_branch()` no-ops
when the remote ref is missing and records (never swallows) a failed push. `repo` is wired
through `prune()` so the CLI's `--repo` drives the `gh` lookups.

## The tick wiring (already on main, tightened)

The orchestrator tick's STEP 10 (landed with the #2262 mandate in PR #2272) already runs
`make worktree-report` → `make worktree-prune CONFIRM=1` → `make check-host-space`. This PR
tightens its /tmp step to call the **canonical `make reclaim-tmp-worktrees DRY=0`** target
(since landed by #2141) instead of hand-rolling the `git merge-base --is-ancestor` check, so
the ancestry-gated /tmp pass is the tested, versioned one; FORCE stays the #794-guarded owner
exception, never a pass step.

## What was verified

`tests/test_worktree_prune.py` gains the issue's cases over `_gh_stub` (now answering
`issue view` from `issues.json`): ancestry-prune (no PR, no issue, head ancestor of base →
branch pruned and remote deleted), open-issue keep, closed/absent-issue prune, head-ahead-of-main
keep (negative control), open-PR keep, merged-remote-deleted, and a live-open-PR-keeps-remote
negative control. `31 passed`. `make reclaim-tmp-worktrees DRY=1` ran clean; `make check-docs`
and `make changes-index` green.
