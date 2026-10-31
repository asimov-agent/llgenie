# Base integrity and merge integrity

Rules for keeping a review verdict tied to a real base, and for confirming a finding
actually landed after a merge.

## Never rebase a branch stacked on a squash-merged ancestor

When the base PR landed as a **squash**, `main` carries one commit while your branch carries
the base PR's whole lineage. `git rebase <new-base>` therefore replays all of it and conflicts
on files that are **not yours** — measured once as `Makefile` plus a dozen foreign `agents/*`
files, none of which the branch had touched.

Correct shape:

```bash
git rebase --abort                     # first, if you already started one
git checkout -B <branch> <new-base>    # sit on the real base
git diff <old-base> <old-head> > p.patch   # YOUR change only
git apply --check p.patch              # clean iff new-base blobs == old-base blobs
git apply p.patch
# re-sync anything sourced from a live copy, then verify and commit
```

`git apply --check` passing is the assertion worth making: it means the new base's blobs equal
your old base's, so your diff is the only delta. If it fails, inspect which path diverged — do
not force it through.

## Re-verify your findings against the merged sha

A defect found on a branch is only fixed once it is fixed **on main**. After a merge, re-run the
specific check that failed and say which of your findings survived:

- a stale golden that was regenerated pre-merge shows as the suite passing on `main`;
- an issue closed as "ruling recorded" is **not** evidence that behaviour changed — re-measure the
  numbers the ruling cites at the merged commit.

Report both outcomes explicitly. "Merged" answers a different question from "the defect is gone".

## A squash merge rewrites the sha — verify content, not ancestry

After a **squash** merge the branch's commits are not on `main`; they are collapsed into one new
commit with a different sha. So `git merge-base --is-ancestor <branch-head> refs/remotes/live/main`
returns **non-zero** for a merge that succeeded, and reading that as "it did not land" is a false
alarm about a PR that is already in.

Verify by **content** instead — the files the PR was supposed to change, at the merged tip:

```bash
git show refs/remotes/live/main:<the/changed/file> | grep -c '<a phrase the change introduced>'
git ls-tree -r --name-only refs/remotes/live/main -- <dir>/ | grep -c '<the file the PR added>'
```

And state which verification you ran, because they answer different questions: `state: MERGED` +
`mergedAt` is the merge decision, ancestry is a property of the commit graph, and only the content
check says the change is in the tree. Quote the merge commit sha beside them.

The same rewrite makes every downstream expectation shift: the merged file may be **older than the
live copy** if work continued on the live side while the PR was in flight, so a `cmp -s` mismatch
after a merge is not a failed merge — it is new drift to version, which is a separate PR.

## A versioned skill is the first time a live skill meets CI

A lane's live skill lives under the agent home, where **nothing lints it**. The first time it is
versioned under `agents/<lane>/skills/`, the repo's gates (`lint_linefeeds.py`, `check-docs`,
`check_wiring`) run over it for the first time — so a live copy can be lint-red indefinitely and
nobody learns until a PR versions it.

Concretely: a `<!-- host-bot-tools:begin -->` marker sitting directly above `## Tools` with no
blank line reds `lint_linefeeds.py` at that heading, because a marker line is not blank. Fix it
in the **live** copy and re-sync, never only in the tree copy: patching the tree alone re-creates
the live-vs-tree drift the versioning PR exists to remove, and the next sync silently reverts it.

Run the repo lints locally before pushing a versioning PR (`python3 scripts/lint_linefeeds.py`,
`make check-docs`) — and expect the first push to find something, because the host copy has never
been checked.

## Do not push while a run at the head is in progress

A CI run at the current head plus a push equals a cancelled run when the workflow sets
`cancel-in-progress`. That turns a legitimate fix into a destroyed matrix: the old run is neither
green nor red, it is **no verdict**, and the reviewer's own rule forbids reading it either way.
Wait for the head's run to conclude, or say explicitly that the push supersedes and a new run is
required. Recording a lesson in a live skill does **not** require pushing it — do that, and defer
the sync to a moment when no run is in flight.

## Diff a PR against its MERGE-BASE, not against `main`

`git diff main...HEAD` and `git diff main..HEAD` both misreport a branch that is merely **behind**
`main`: the two-dot form shows every file that landed on main since the branch forked, so a PR's
own change is buried among dozens of unrelated files and a real finding can be attributed to the
wrong PR (measured twice in one evening: two PRs each looked like they touched 20+ `agent-wiki/`
files that had actually arrived via another PR's merge).

Use the merge-base:

```bash
MB=$(git merge-base refs/remotes/live/main HEAD)
git diff --name-only "$MB" HEAD        # what THIS branch changed
git diff "$MB" HEAD                    # the same, with content
```

Then state the merge-base sha next to `main`, e.g. "measured against merge-base `36cfa8c1`
(main is `ac12cae9`)" — a reviewer reading a file list needs to know which base produced it.
The three-dot form (`main...HEAD`) is equivalent to the merge-base call and is fine, but naming
the sha removes the ambiguity entirely.

A branch being behind `main` is **not** itself a `CONFLICTING` state, so per the fleet's rebase
rule it is not a reason to rewrite — but it does mean CI at that head ran against a superseded
base, which changes how a red may be attributed.

## A rebase can clear the conflict and leave the cause

`mergeStateStatus` going `DIRTY → BLOCKED` after a rebase is **not** evidence that the problem was
fixed. A rebase re-applies your change onto the new base; if the base's version of the contested
file moved, the same hunk can now apply without a textual collision. The commit still carries it.

Measured: a PR `DIRTY` on `CHANGES.md` was rebased onto the new `main`, went `BLOCKED`, and
`git diff --name-only "$(git merge-base main HEAD)" HEAD | grep -c '^CHANGES.md$'` still returned
`1` with the same appended row. It will go `DIRTY` again the next time that file changes on main.

So after a rebase that “clears” a conflict, re-run the same check that found it:

```bash
MB=$(git merge-base refs/remotes/live/main HEAD)
git diff --name-only "$MB" HEAD      # is the offending path still in the diff?
git merge-tree --write-tree refs/remotes/live/main HEAD   # does it merge RIGHT NOW?
```

"Merges right now" and "no longer carries the defect" are different claims. Report them separately,
and credit the rebase for clearing a real conflict while saying the underlying change is still
there — otherwise `BLOCKED` reads as repaired and the defect ships.

## Render a shared append AFTER rebasing, never before

A generated aggregate that every PR appends to (`CHANGES.md` and its fragment renderer are the
canonical case) is a **shared append**, and its generator is deterministic against the fragment set
*on the base it reads*. So rendering on the stale base writes a file whose rows sit where the old
base put them, and landing that on a moved `main` produces a conflict in the very file the rebase
existed to escape. Measured: `make changes-index` on the pre-rebase tree → `git merge-tree` against
the new tip reported **1 conflict**, in `CHANGES.md` alone.

Correct order, every time:

```bash
git checkout -B <branch> refs/remotes/live/main   # or re-apply your diff onto it
make changes-index                                 # render from the base you will target
python3 -m pytest <the aggregate's own test> -q    # the render is only correct if this passes
```

Corollary: if a rebase is required for any reason, re-render afterwards even when you rendered
before — the earlier render is now a claim about a base that no longer exists.

## Test the MERGED RESULT, not the merge

A textual `git merge-tree` answers *"do these two hunks collide"*, not *"is the result correct"*. An
invariant that holds over a **rendered file** — a committed aggregate equal to its render, a manifest
equal to its inventory — can fail on the merged tree even when the merge is textually clean, because
each side rendered against its own base and the composition of two correct renders is not necessarily
a correct render.

So when `main` moves under an open PR, do not stop at `merge-tree`. Build the merge and run the check
on the result:

```bash
git worktree add --detach /tmp/mg refs/remotes/live/main
cd /tmp/mg && git merge --no-commit <head>
python3 -m pytest <the invariant's own test> -q
```

"No conflicts" and "the merged result passes" are different claims. The first is cheap; the second is
the one that decides whether a re-cut is needed — and it frequently answers *no* when intuition says
yes, which is a matrix saved rather than a risk taken. Do not let "the base moved" stand in for
"the merged result fails": only the second is a rebase trigger.

## An arm records a time, never a head

`autoMergeRequest.enabledAt` is stamped when someone enables auto-merge and is **not** cleared by a
later push. Measured: one arm timestamp survived **three** head moves, including a head where the
deciding gate had been cancelled and never executed.

So the field answers *"was an arm requested"*, never *"is this head armed"*. Report arm state with the
head beside it, and treat an arm older than the current head as **unverified** rather than as intent to
merge the current one. When you read someone else's "it's armed" claim, the same gap applies: a live
`enabledAt` says nothing about which sha it applies to, so neither party can conclude from it that the
present head will merge.

## Quote the base at the moment of the claim

Every finding, control and verdict is relative to a base sha. Read it (`git fetch origin
refs/heads/main:refs/remotes/live/main` then `gh api .../commits/main --jq .sha`, and require them
to match) *in the same turn* as the claim. A clean merge at a superseded base proves nothing about
the base you will target; a control run against yesterday's main proves nothing about today's.
