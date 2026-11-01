# Fork PR: fetch, rebase, verify, push to the branch's own remote

Use when a PR's head branch lives on a fork (`gh pr view --json headRepository` → `isCrossRepository=true`), i.e. the owner's `andyholst/llgenie`, not the canonical `asimov-agent/llgenie`.

## 1. Resolve the head repo — never assume `origin` has the ref

`git fetch origin refs/heads/<branch>` fails with `fatal: couldn't find remote ref` for a fork PR: the branch exists only on the fork. Resolve it from the API first:

```
gh pr view <n> --repo asimov-agent/llgenie --json headRepositoryOwner,headRepository,isCrossRepository,headRefOid
# → headRepository.nameWithOwner = andyholst/llgenie, isCrossRepository = true
```

Then fetch by the configured remote name (`fork`), not by the `nameWithOwner` URL — the URL form fails when the local remote is already aliased:

```
git fetch fork +refs/heads/<branch>:refs/remotes/fork/<branch>
git rev-parse --short refs/remotes/fork/<branch>   # must equal the PR headRefOid
```

## 2. Rebase in a throwaway worktree, base = the main sha you fetched this moment

```
git worktree add -B pr<n>-rebase <path>/pr<n> refs/remotes/fork/<branch>
cd <path>/pr<n>
git fetch origin +refs/heads/main:refs/remotes/origin/main --quiet
M=$(git rev-parse refs/remotes/origin/main)   # branch from THIS sha, never a quoted one
git rebase "$M"
```

## 3. Fidelity gate BEFORE the push (a clean rc=0 is not proof)

A token-level rebase can silently drop one side; verify all four:

```
M=$(git rev-parse refs/remotes/origin/main)
git rev-parse HEAD^                                   # == $M (single commit on the new base)
git rev-parse --short HEAD                            # new head sha
OLD=$(git rev-parse refs/remotes/fork/<branch>)       # old PR head, before rebase
git diff --name-only "$M" HEAD                        # expected file set only
git diff --numstat "$M" HEAD | awk '{i+=$1;d+=$2} END{print i,d}'   # matches the rehearsed delta
git grep -lE '^(<<<<<<<|>>>>>>>)' | wc -l             # 0
for f in $(git diff --name-only "$M" HEAD); do
  [ "$(git show HEAD:$f)" = "$(git show $OLD:$f)" ] && echo "IDENT $f" || echo "DIFFERS $f"
done   # every changed file byte-identical to the old head = a mechanical rebase, not a rewrite
```

A file that DIFFERS from the old head means you changed content, not replayed it — stop and explain before pushing.

## 4. Push only to the branch's own remote, with lease

```
git push --force-with-lease fork HEAD:refs/heads/<branch>
# then confirm local==remote: git ls-remote fork refs/heads/<branch>
```

Never push a fork PR's branch to `origin` (asimov-agent) — `origin` is upstream `main` only. Never `--force` bare; a rejected lease means another actor moved the branch → re-fetch, re-measure, report, stop.

## 5. Read-back is racy right after a force-push

`gh pr view --json headRefOid` may still show the old sha or UNKNOWN while GitHub recomputes the merge ref. Re-read after a short wait; only report the head once it matches the sha you pushed. A PR that stays `mss=BLOCKED` after landing on a newer main is fine under #1015 — leave MERGEABLE/BLOCKED alone, do not pre-emptively rebase again.

## 6. Another lane's vehicle: no arm, no prune

A rebase-only dispatch ("rebase and force-push only") is not an arm invitation. Leave the worktree for the owner, do not prune it, do not arm auto-merge on a branch this lane does not own. Post START + FINISH bookends and report head sha + fresh run ids to the planner.
