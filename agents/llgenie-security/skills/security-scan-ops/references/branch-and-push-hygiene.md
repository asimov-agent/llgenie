# Branch, push and worktree hygiene (security lane)

A commit on the wrong branch looks like an empty PR; a reset on the wrong branch destroys other lanes'
work. Both are cheap to prevent and expensive to diagnose.

## Before any history rewrite

```bash
git branch --show-current                  # must be the branch you were dispatched for
git log --oneline <base>..HEAD             # must list EXACTLY the commits you own
```

On a shared checkout left on `main`, `<base>..HEAD` silently expands to other sessions' merged work and a
rebase rewrites them. Abort on the first unexpected conflict, then prove `main` is untouched:

```bash
git reflog show main
git log --oneline origin/main..main
```

`git checkout -b <branch> && git rm …` only lands you on `<branch>` if the checkout itself succeeded; when
the `rm` is the thing that fails, the checkout already happened and a later stray `git checkout main` puts
you back — so the next `git commit` lands on `main`. It surfaces as `gh pr create` saying **"No commits
between main and <branch>"**, which means *your commit never reached the branch*, not that the branch is
empty.

```bash
git status -sb                            # BEFORE committing: header must name your branch
git branch -f <branch> HEAD && git reset --hard origin/main && git checkout <branch>
git push origin HEAD:<branch>
git log --oneline origin/<branch> -2       # AFTER pushing: your commit must be in it
```

## Re-authoring your own commits (identity gate)

The allowlist is name→email PAIRS (`Andy Holst <andy.holst@protonmail.com>`, `Asimov Agent
<support@docondee.com>`). A right name with an invented address still reds `check-pr-authors` in `make
ci-unit`. Quote both, and rewrite only your own range:

```bash
git -c 'user.name="Asimov Agent"' -c user.email=support@docondee.com rebase <base> --exec \
  'git -c "user.name=Asimov Agent" -c user.email=support@docondee.com commit --amend --no-edit \
   --author="Asimov Agent <support@docondee.com>" -q'
git push --force-with-lease=<branch>:<old-sha> --force-if-includes origin HEAD:<branch>
```

- Force-push only after a fetch and only when `statusCheckRollup` shows **0 in-progress runs** at the old head.
- `-c user.email=…` overrides config by design, so no config sweep finds a bad identity: audit the commits
  (`gh api repos/<r>/pulls/<n>/commits`) and check your own PRs first.
- An off-allowlist commit is environment config, not a repo edit: verify the address is absent from the tree
  (`grep -rn '<email>' --include=*.py --include=*.yml …`), report the sha and address, and propose the amend
  in the *producing* lane. Widening the allowlist is the weakening this lane refuses.

## Stale worktree, or unique work? Prove it, then re-point

A sweep reporting `ahead N / behind M` is **not** evidence of lost work: an older base guarantees a
non-empty tree diff. Classify every differing file before touching anything:

```bash
python3 scripts/worktree_divergence_audit.py --worktree /path/to/wt \
  --target origin/<pr-branch> --main origin/main        # exit 1 == unique lines exist
```

1. **Blob equality against three sources** — the target ref, `main`, and the local chain's own base — plus
   "does this blob occur anywhere in `main`'s history" (`git rev-list --objects main -- <path>`).
2. **Line-set containment** for whatever matches nothing: `diff base..HEAD` adds/removes ⊆
   `diff base..<target>` adds/removes. All-contained means an older variant; any line the target lacks is
   genuinely unique.

Blob equality alone is insufficient in both directions: a file can be byte-identical to a stale base *and*
to `main`, and a file matching no single ref can still be older. Containment is decisive; report its numbers
(`+0 unique adds, -0 unique removes`) rather than a judgement.

If nothing is unique: `git -C <wt> reset --hard <target>` — **never a force-push** — after confirming
`git status --porcelain` is empty, then verify `HEAD` equals the target, the branch is in sync, and the
tree's own gate is green. Unique work goes in a push, not a reset, and is reported before anything moves.

## A merge can exist in no reachable history — check ancestry, not just the PR state

`state=MERGED` in the tracker is not proof the change survived: a later force-push of the base branch strands
the merge commit, and `gh pr view` keeps saying MERGED forever because the PR record is independent of the
commit graph. This is the failure mode of several lanes merging into one consolidation branch that is then
rebased underneath them.

```bash
gh pr view <n> --json number,state,mergedAt,mergeCommit
git merge-base --is-ancestor <mergeCommit> origin/main && echo "in main" || echo "STRANDED from main"
git merge-base --is-ancestor <mergeCommit> origin/<shared-branch>          # and from the branch it merged into
```

Stranded-but-present means the *content* survives only because a later commit carried it — prove that
explicitly (grep the file at the current head for the lines you added) and say so, because `git log` can no
longer show that anything was reviewed. A branch that other lanes merge into is never force-pushed
unilaterally; a rebase of it is a conversation with those lanes first.

## An interrupted rebase is not an invalid one

If a worktree is mid-rebase (`rebase-merge/` present, "interactive rebase in progress; onto <sha>"), read
`git status` and the conflict before deciding anything: continuing a correctly resolved conflict keeps work
that a restart throws away. Abort only when the direction itself is wrong — the wrong branch, the wrong base.
