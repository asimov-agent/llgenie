# Batch-rebasing open PRs against a moved `main`

Owner-ordered sweep: fetch latest `main`, rebase every open PR onto it, resolve conflicts one at
a time. The reviewer normally does not push; this fires when the owner explicitly issues it as a
maintenance dispatch. Work strictly ONE PR at a time.

## Per-PR order of operations

```bash
R=asimov-agent/llgenie
# 1. ALWAYS re-read the head via the API; `gh pr list` values go stale fast (branches move under you)
head=$(gh api repos/$R/pulls/<n> --jq .head.sha)
br=$(gh api repos/$R/pulls/<n> --jq .head.ref)
repo=$(gh api repos/$R/pulls/<n> --jq .head.repo.full_name)   # decide the push target NOW

git -C "$HOME/repository/git/llgenie" worktree add --detach ../../llgenie-wt/rb<n> "$head"
cd "$HOME/repository/git/llgenie-wt/rb<n>"

# 2. skip if already current (merge-base == origin/main) -> `git rebase` says "up to date" fast
mb=$(git merge-base HEAD origin/main); [ "$mb" = "$(git rev-parse origin/main)" ] && echo "current, skip"

GIT_EDITOR=true git rebase origin/main     # silent edits; a commit-message prompt hangs otherwise
# stacked PRs (base != main) rebase onto the stack branch head, not main:
#   git fetch origin refs/heads/<stack>:refs/remotes/stack/head
#   GIT_EDITOR=true git rebase refs/remotes/stack/head
```

## CHANGES.md conflicts — the canonical fix, never hand-merge the table

The one-row-per-file changes index makes `CHANGES.md` *generated output*. A branch that predates it
(or that hand-edited the table) conflicts there with a row layout that hand-editing corrupts.
Resolve by treating the fragment directory as the source of truth:

```bash
# conflict is UU CHANGES.md -> keep the applied side, regenerate from docs/changes.d/
git checkout HEAD -- CHANGES.md && make changes-index && git add -A
GIT_EDITOR=true git rebase --continue
```

If the fragment `docs/changes.d/<change>.md` is missing from the branch entirely (a pre-directory
base), create it as a single table row whose `[name](agent-wiki/<change>.md)` link matches the wiki
note, then regenerate. Equal `agent-wiki`/`changes.d` counts must hold at the end:
`pr_watch.py --changes-index origin/main <new-head>` must print no `SHORT` verdict.

## `git rebase --continue` can hang mid-commit — finish by hand

`--continue` sometimes stalls (hooks/editor) after it has already written the tree and the index,
leaving `HEAD` at `origin/main` with the PR's files staged and `status` showing `M`/`A`. Confirm:
`git log -1` shows the main sha and `git diff --cached` has the PR content. Then finish the commit
manually with the original author/message rather than looping on `--continue`:

```bash
git commit -q -C <original-pr-head-sha>      # after: git log -1 --format='%h %s' is the rebased PR commit
```

Afterwards append any missing changes.d fragment, `make changes-index`, and re-commit (amend).
Never leave the worktree half-committed.

## Push target: fork vs origin — decide before you push anything

```bash
repo=$(gh api repos/$R/pulls/<n> --jq .head.repo.full_name)
# head lives on asimov-agent/llgenie -> origin; on andyholst/llgenie -> fork
remote=origin; [ "$repo" = "andyholst/llgenie" ] && remote=fork
git push --force-with-lease "$remote" HEAD:refs/heads/$br
```

Pushing a fork-head PR's rebase to `origin` does NOT update the PR — it creates or force-updates a
same-named branch on the BASE repo that no PR uses. If that happens, restore the base branch to its
true prior sha (captured as `git ls-remote origin refs/heads/$br` before pushing) or delete it if it
was created fresh, then push to the fork instead. Catch it with the head-repo API read at step 1; do
not guess from the branch name.

## Verify after the rebase, before the push is believed

```bash
python3 scripts/check_pr_authors.py check --base origin/main --head HEAD   # or --base refs/remotes/stack/head
# stacked PRs can carry off-allowlist commits (`Andy <...>` missing surname): fix per commit with
#   git -c user.name='Andy Holst' -c user.email='andy.holst@protonmail.com' commit --amend --no-edit --reset-author
# for a middle commit, use an interactive rebase with an exec line; then re-run the authors gate
python3 -m pytest tests/test_changes_index.py tests/test_check_docs.py -q -p no:cacheprovider --noconftest
```

**A LANE whose whole identity is off the allowlist is an owner flag, not a silent rewrite.** When the
author is a lane-name identity that is not `Andy Holst` or `Asimov Agent` at all (e.g.
`LLGenie Architect <architect@llgenie.local>`), `--reset-author` to the allowed bot pair makes the
rebase land, but re-authoring another lane's commits as *this* reviewer is overriding their
attribution — the durable fix is to add that lane's identity to `scripts/check_pr_authors.ALLOWED`
or have the lane commit under an allowed identity. Do the rebase (the owner ordered it), state in the
report that each such commit was re-authored to the single allowed bot identity and `git log` shows
it, and hand the allowlist gap to the planner/owner rather than making it routine policy.**

**The PR-head API lags a fresh force-push.** Right after pushing, `gh api .../pulls/<n> --jq .head.sha`
can still report the OLD sha while `git ls-remote $remote refs/heads/$br` already shows the new one.
Verify with the ref read (+ a short sleep), not the PR API alone, before you claim a PR moved.

**A red that predates the rebase is not introduced by it.** A `check_docs`/`changes-index` failure at
the rebased head that ALSO fails on the pre-rebase head is the PR's own (or `main`'s) pre-existing
state; prove it (`worktree add` the original head, run the same module) and say so rather than
treating the regen as the cause.

## A force-with-lease reject in the middle of a sweep is a peer move — check ancestry, do not blind-force

`git push --force-with-lease ...` answering `(stale info)` / `[rejected]` is the guard refusing to
overwrite a ref that changed since your last fetch — treat that as a sign, not a hurdle. Fetch the
target ref, compare the new tip to your rebased head:

```bash
forknow=$(git ls-remote $remote refs/heads/$br | cut -d' ' -f1)
git merge-base --is-ancestor "$myhead" "$forknow" && echo "newer commit is ON TOP of mine (peer pushed over/after)" \
  || echo "tip is an unrelated/older base — force would drop peer work"
git log --oneline "$myhead..$forknow"   # read what you would destroy
```

If the branch tip carries a commit that is **not** an ancestor of your rebase (a peer lane committed
on it, on a base your rebase did not include), your push would **drop that commit**. Counts far more
than a failed rebase: stop, leave the branch, and report it as "live peer branch, not stale" rather
than resolving the lease with a blind force. A branch that looks stale in the merge-base sense can
still be actively worked by the lane that owns it; the force-with-lease guard is the only thing
between that and data loss. This is the same never-clobber-a-peer rule as review, applied mid-sweep.

## Measure staleness with full SHAs — a bad measurement that flags everything is worse than none

When checking which of a board of PRs needs a rebase, feed `git merge-base` / `git merge-base
--is-ancestor` the **full 40-char** heads, never truncated 8-char strings and never a reconstructed
sha (`"$h"+"0"*32`). A loop that passes short/patched shas makes every ancestry test fail, which
misclassifies **every** open PR (including ones verified on current main) as stale — an all-stale
board is indistinguishable from a measurement bug, and acting on it would force-push a dozen
no-op rebases. Build the check to prove the negative: count `current` PRs (`merge-base --is-ancestor
<full-main> <full-head>` True) and report how many that is, so a measurement that returns zero
current reveals its own bug instead of looking like a green light to rewrite the board.

## Sweep bookkeeping

- Keep a table: PR -> remote -> head sha; after each push re-read every head from the API and assert
  `want == cur`. 20-30 PRs, one call each, catches a mis-routed or lagged push.
- A `DIRTY`/`BLOCKED` status is NOT a guarantee of staleness — some are already on current main
  (`merge-base` check) and must not be force-pushed as a no-op.
- `do-not-merge` labels stay untouched during the sweep: rebase the PR, do not lift or re-place the
  tag, and say so in the report.
- Leave pre-existing registered worktrees in place (owner prunes); remove only the ones this sweep
  created.
