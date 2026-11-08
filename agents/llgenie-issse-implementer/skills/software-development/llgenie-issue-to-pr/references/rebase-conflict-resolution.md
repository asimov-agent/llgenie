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

## A conflict-free rebase can still be semantically broken — baseline pristine main before believing a red

A rebase that CLEANLY replays your commit (zero `<<<<<<<` markers) can still produce a wrong
tree: main merged a feature that RENAMED or reshaped a seam your commit or its tests rely on,
and git saw no textual overlap. Tell: a test reds at the new head with no conflict — e.g. a test
fixture that patched `_sh` now hits the real docker run because the rebased code streams through
`_sh_live` instead. The rebase said "successfully rebased" and was still wrong.

Discriminate a REAL regression from a container/clone artefact with a three-way baseline BEFORE
touching code:

1. Run the failing test file at pristine `origin/main` (detached checkout) — must PASS.
2. Run it at your rebased head — FAILS.
3. That delta IS your merge defect even though the rebase was clean. This is the only way to
   separate "my rebase broke it" from "this container cannot run it" — never wave a post-rebase
   red away as environmental without step 1.

Fix: `grep` for the renamed symbol to find the seam that moved, patch the OLD caller to the NEW
seam (patch BOTH the old and new names in a fake, mirroring whatever the surviving fixture already
does), amend, re-run to green on a full clone.

## Confirm a genuine conflict first

`git merge-tree --write-tree origin/main HEAD` with zero `CONFLICT` lines means there is
no real content conflict — never rebase to satisfy a guard or a `mergeable_state=dirty`
that a fresh regenerate already resolves. Only rebase on a true conflict or a merged base
(issue #1015: do not chase every main move).

## Measure the conflict surface before declaring it real

Classify a `CONFLICTING`/`DIRTY` PR by intersecting what YOUR PR changes with what landed
on main since your base. The size of that intersection says whether the rebase is a
mechanical changelog union or a real logic collision — and lets you tell the rebase lane
exactly what to expect instead of a vague "please rebase".

```bash
gh pr view <n> --repo O/R --json files --jq '[.files[].path]'          # your PR's files
gh api repos/O/R/compare/<baseSha>...<mainTipSha> --jq '[.files[].filename]'  # moved on main
# intersect the two sets: ONLY those files can conflict
```

If the intersection is only `CHANGES.md` (the shared-append index regenerates by union),
the conflict is mechanical — say so and name the fix; do not churn. A real logic conflict
is `scripts/`, `tests/`, or the feature's own `openspec/changes/<slug>/` appearing in the
intersection.

## A lane-owned rebase: hand measured intel, do not rebase it yourself

When the dispatch assigns the rebase to another lane (a merge-conflict/`-rebase` lane) or
the branch is under another lane's active edit, you do not push or force it. Post the
measured overlap (the intersection above, with the base and main shas) on the issue AND
message that lane: it turns their "rebase this" into a known-cheap union. A force-push of
a branch another lane is working rewrites shas under their feet; a rebase request with no
measurement is what stalls a lane.

## A `git rebase --continue` that stops to edit the message hangs forever on a non-interactive call

`git rebase --continue` opens the commit-message editor when the replayed commit's message
needs confirmation. On a backgrounded/`terminal` call there is no TTY, so it blocks with no
output — it looks like a hung rebase, not a prompt, and a background job can sit there until
killed. Rule: run the continuation in the FOREGROUND with the editor neutralised, keeping the
existing message:

    GIT_EDITOR=true git rebase --continue

If a background continuation is already blocked, kill it and re-run that way — do NOT
`git rebase --abort` (the commit has usually already landed; see the marker section above).

## When main already superseded your exact change, resolve to main and drop yours

A conflict on the exact line your commit rewrote often means main merged a better /
authoritative version of the same intent while your branch sat. Do not force your older
value back in to "keep your change". Resolve to MAIN's version — that is the ruling that
landed — then remove your now-redundant change so the rebase replays clean. Prove the drop
with `git diff origin/main HEAD -- <that file>` = empty, and prove nothing else was lost by
checking every other substantive file still differs. Taking main's side is not losing work;
re-asserting your superseded line is the defect.

## After a conflict-caused rebase, the PR body's head/base facts go stale

The body's `**Head:** \`<sha>\` on \`origin/main\` \`<sha>\`` paragraph and any bullet
describing a change main has since absorbed now describe the OLD head. Re-run `make
bot-preflight` and copy the `AGENTS:`/`BASE:` literals it prints (they now read the new
base), then PATCH the body so the head sha, base sha, and the superseded bullet all match
the rebased wire head. A body citing a head no longer on the branch misleads the reviewer
and can red `check-pr-agents-line` / `check-pr-base`.

## Right after a force-push, `mergeable` reads `null` / `unknown` for a few seconds

The PR API can return `mergeable: null, mergeable_state: unknown` while GitHub recomputes
the new head. Read it back once more before concluding anything
(`gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha, base:.base.sha, commits, mergeable, mergeable_state}'`);
stable values arrive within seconds. Never report `unknown` as a verdict, and never read
`mergeable_state=blocked` with required checks still `in_progress` as a failure — that is
the normal running state.
