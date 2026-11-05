# Rebase conflict — resolve without corrupting the base

When a rebase stops on a conflict (most often `CHANGES.md`, because both main and your
branch re-rendered the shared-append index), resolve it correctly and then re-establish
the ancestor relationship before pushing. Getting this wrong produces a tree that looks
perfect but fails `check-pr-base`.

## The amend trap (the expensive one)

**Never `git commit --amend` while a rebase is mid-conflict.** A rebase that stopped on a
conflict leaves you in an "editing a commit" state; the correct continuation is
`git add <resolved>` then `git rebase --continue`. Running `git add -A && git commit --amend`
from that state attaches your change to the WRONG parent and yields a HEAD that is a
**sibling** of `origin/main`, not a child of it. Symptoms:

- `git diff --stat origin/main..HEAD` shows exactly your intended files — looks correct.
- `git merge-base --is-ancestor origin/main HEAD` returns **NO** (rc 1).
- `check-pr-base` reds with "shares no common ancestor with origin/main", even though the
  branch's real content sits on top of main.
- `git log --format='%h %p %s' -1 HEAD` shows a parent that is a main commit but the
  subject/committer pairing is off — the amend reused the wrong commit's identity.

## Recovery (branch already pushed / under review — do not force-push the broken head)

```bash
# pointer onto the live tip, keep your working-tree change as uncommitted edits
git reset --mixed origin/main
# regenerate any shared-append file from fragments (never hand-merge <<<<<<< markers)
make changes-index                 # or the repo's index-regeneration target
git add -A
git commit -m '<same title> (closes #<n>)'
# prove the base relationship is now correct BEFORE pushing
git merge-base --is-ancestor origin/main HEAD && echo ancestor-OK
make bot-preflight                 # re-reads the fresh AGENTS/BASE literal
```

Then push (force-with-lease, since the broken head was already on the fork) and confirm
the base gate greens at the new head. See `references/mechanical-index-regeneration.md`
for the CHANGES.md-from-fragments detail and `references/pr-body-and-base-gates.md` for
the AGENTS/BASE literals the preflight must match.

## Resolving a CHANGES.md conflict

This file is generated, so do not merge the conflict markers by hand. Regenerate it from
the fragment directory at the NEW base (`make changes-index` reads every fragment and
rewrites the index), which incorporates both main's rows and your new fragment. The
resulting count is whatever the generator emits — quote that count verbatim in the PR
body; it moves every time main lands another fragment.

## A rebase that reported an error can leave the marker AFTER the work already landed

A wrapped/scripted rebase can exit non-zero (an exec or unpack error) while the rebase itself
succeeded: HEAD is already a child of the new main and your commit is intact. `git status` then
still prints "rebase in progress" / "You are currently editing a commit", and a leftover
`.git/rebase-merge` directory exists.

- Decide from TOPOLOGY, never from `git status`: `git log -1 --format='%h %p %s'` (parent must be
  the new main) plus `git merge-base origin/main HEAD` == `git rev-parse origin/main`.
- If the topology and files are correct with a clean tree, finish it with `git rebase --continue`.
  **Never `git rebase --abort`** here — abort throws away the commit that already landed correctly.
  Never hand-delete the marker directory either.
- Only after the marker is gone, re-run `make check-pr-base` and the gate set at the new head;
  a "measurement" taken while the marker exists describes a half-state, not the branch.

## Confirm a genuine conflict first

`git merge-tree --write-tree origin/main HEAD` with zero `CONFLICT` lines means there is
no real content conflict — never rebase to satisfy a guard or a `mergeable_state=dirty`
that a fresh regenerate already resolves. Only rebase on a true conflict or a merged base
(issue #1015: do not chase every main move).
