# When a rebase is genuinely owed: the `check-pr-base` gate

SKILL.md's step 4 says "rebase only when `mergeable == CONFLICTING`, don't chase main". That is the
default. Two things override it: the `check-pr-base` gate below, and an explicit owner/planner
ORDER to rebase (a directive to keep the base current is not chasing — but see the stage-don't-push
rule when a run is in flight). The gate is the most common reason a MERGEABLE-but-behind branch
still has to be rebased.

## The rule

`check-pr-base` (issue #845) requires

```
git merge-base origin/main HEAD   ==   git rev-parse origin/main
```

so the instant ANY peer PR merges into `main`, `merge-base` falls behind the live tip and the gate
reds against your branch. A green therefore *requires* merge-base==base, and a rebase is genuinely
owed to get there — this is not discretionary chasing, it is the gate's acceptance criterion.

Measure it exactly before touching anything:

```
mb=$(git -C <wt> merge-base origin/main HEAD)
main=$(git -C <wt> rev-parse origin/main)
[ "$mb" = "$main" ] && echo "gate satisfied — NO rebase due" || echo "rebase owed (merge-base != main)"
```

When they are equal, the gate is satisfied even if `gh pr view --json mergeStateStatus` reads
`behind` — do NOT rebase (that is the no-chase rule, and issue #1015 forbids churn). When they
differ, the rebase is the owed work.

## The gate reads `origin/main` AT GATE-RUN TIME — re-check just before pushing, and re-rebase if main moved while CI queued

A branch cut from the then-live tip STILL reds `check-pr-base` if a peer merges into `main`
between your push and the guard run: the gate compares `merge-base origin/main HEAD` against the
`origin/main` it reads when the JOB runs, not the sha you branched from. Symptom: local
`merge-base==main` was true at push time, then guard reds with "measured against `origin/main`
at `<newer sha>`" and lists your commit as "foreign".

- Fetch and re-check `git merge-base origin/main HEAD == git rev-parse origin/main` IMMEDIATELY
  before force-pushing — not only when you started the work.
- If it reds AFTER a push, the fix is a SECOND rebase onto the newer tip:
  `git fetch origin +refs/heads/main:refs/remotes/origin/main && GIT_EDITOR=true git rebase origin/main`,
  a fresh clean replay, a re-run of the touched tests, another force-push. Do not argue the gate
  is stale — main really moved and the gate is right. A MERGEABLE-but-red `check-pr-base` is not
  a GitHub flake.
- Re-prove `merge-base==main` AND that any hand-merged fix survived the re-rebase (grep for the
  resolved symbol) before re-pushing — a rebase does not preserve edits you made in the working
  tree, only committed ones; re-check the tree, do not assume.

## It fires on doc-only peer merges too

A peer merger of `openspec/Dockerfile` + its change-note trio still moves the base sha, so
`check-pr-base` reds even though none of those files overlap yours. The rebase is clean except for
any shared-append file:

- `CHANGES.md` is a RENDERED file. A rebase conflicts because both the peer's row and your row
  append to the same table. Keep BOTH sets of rows in the working tree, then re-render from the
  fragments: `make changes-index` (benedictional). `tests/test_changes_index.py` demands the
  renderer's OUTPUT byte-for-byte — a hand-merged marker set reds it — so never resolve the markers
  by hand and commit; resolve, then render.

## An ORDERED rebase on a MERGEABLE branch is a third override — but stage, don't push, while a run is in flight

An owner/planner directive to rebase onto the latest main is a legitimate override of the no-chase
default EVEN when `mergeable == true` (no file conflict): the directive is about keeping the base
current, not about a conflict. Accept it — but the directive does NOT license an immediate
force-push if a CI run (a verdict cell, a `push=true` workflow_dispatch, a fresh trigger) is IN
FLIGHT at the tipped head. `cancel-in-progress` makes a push over a live run destructive, and a run
that is compiling the current head is the ground truth you must not clobber.

So when the order arrives with a run in flight:

1. **Stage the rebase in the worktree, hold the push.** Rebase locally
   (`git rebase --onto origin/main <old-merge-base>`), leaving `origin/<branch>` untouched. The
   proof you have NOT pushed is `git rev-parse --short origin/<branch>` still reading the OLD head
   after the rebase — a rebase that moved the remote would be live already.
2. **Stash any deliberate uncommitted working-tree hold BEFORE the rebase** so it does not get
   swept into the rebased commits (`git stash push -m '<reason>' <path>`), then re-apply after. A
   held edit that rides the rebase silently changes the branch's reviewed content.
3. **Verify byte-identity of the substantive files vs the old head:**
   `git diff <old-head> <new-head> --stat -- <each reviewed file>` must be EMPTY. After a clean
   rebase the only tree difference vs the old head is what main itself added (a peer's merged
   files + its CHANGES.md row) — those show in `git diff <old-head> <new-head> --stat` and are
   expected; YOUR reviewed files showing any diff is a defect to fix before reporting.
4. **Report the planned base sha, planned head sha, and what LICENSES the push** (the in-flight
   run concluding, or explicit owner go) — do not push until one of those fires. After it
   concludes: force-push with the lease pinned to the fetched old head, and do NOT re-dispatch a
   second vehicle on top (the two-vehicle rule).

## Sequence

1. Confirm merge-base != main (above).
2. `git rebase origin/main`; on a CHANGES.md conflict keep all rows, `git add`, continue.
3. `make changes-index` to re-render CHANGES.md from fragments (do not hand-edit it).
4. Re-run the fast gates at the new head (registry / engine-gap / quant-catalog / strata / agents-line).
5. `git commit --amend --no-edit` when the re-render changed the tree, then confirm merge-base==main again.
6. Force-push with `--force-with-lease` pinned to the OLD remote sha (read it fresh with
   `git ls-remote origin refs/heads/<b>` first), verify LOCAL==ORIGIN==FORK==new head, and re-chase
   CI at the NEW sha — a run at the old head proves nothing and its watcher is now moot.
