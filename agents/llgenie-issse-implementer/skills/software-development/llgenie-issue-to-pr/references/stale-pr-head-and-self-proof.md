# Stale PR head & independent proof

Two failure modes where GitHub's or CI's view of your head is NOT your working head.
Measure before acting; never assume.

## 1. A cross-fork force-push can leave `refs/pull/<n>/head` pinned to the OLD sha

After a rebase you force-push the fork branch. `git ls-remote <fork> <branch>` and the
fork's branches/refs API both show the NEW sha, but the parent repo's PR head — the PR
`head.sha`, `GET repos/<o>/<r>/git/ref/pull/<n>/head`, GraphQL — stays on the OLD sha,
and the timeline shows no `synchronize` event.

- **Confirm the disagreement across oracles first**: fork ref (`git ls-remote` + API) vs
  PR head (`gh pr view <n> --json headRefOid`, or the `git/ref/pull/<n>/head` endpoint).
  Fork new + PR head old + no synchronize event = GitHub's cross-fork reconciliation lag,
  NOT a real conflict and NOT a bad push.
- **Do not loop re-pushing the same sha** — it is a no-op and will not move the PR head.
- **Fix that works: push a NEW commit sha.** A content-empty commit
  (`git commit --allow-empty -m "ci: re-sync"`) moves the head sha and GitHub reconciles
  the PR to it. The empty commit is benign: the owner's squash merge drops it from main's
  history, so it costs nothing in the merged tree.
- **Do not force-push back to the pre-rebase sha to "clean up".** That is the sha
  reconciliation failed on; bouncing back re-sticks the PR head, leaving it pointing at a
  sha no longer on the fork — a strictly worse state than one benign marker commit at the tip.

## 2. When CI skipped the leg whose proof you need, prove it yourself

An earlier stage (e.g. `scope`) can short-circuit on a red so the later `linux / unit` leg
never runs — the suite was never exercised at your head and no green verdict exists for it.
Do not describe the suite as green; produce the proof.

- **Full hermetic suite**: `make test-unit` in the worktree (docker test image). It takes
  ~8–9 min — over the 420 s foreground clamp. Run it backgrounded
  (`terminal` background + `notify_on_complete`), then `process_manage` wait; read the log
  tail and the `EXIT=` marker with `cat`/`tail`, never by re-running the whole suite to
  "see the result".
- **Independent proof of what was pushed**: clone the FORK branch fresh
  (`git clone -b <branch> --single-branch <fork-url> <scratch>`), then in that clean-room
  checkout (a) `git diff <base>..HEAD --name-only` must be exactly the intended files (no
  stray `agents/` or unrelated churn), and (b) rerun the targeted tests plus the real-world
  repro. This measures the artifact a stranger receives, not your mutable working tree.
- **This clean-room clone is the sanctioned "measure the pushed artifact from an independent
  source" move** when a mutation guard keeps firing on a delivery whose real changes all went
  through `git`/`gh` subprocesses. Do the clone-and-verify proof, then hold — do NOT fabricate
  a file edit to flip a monitor that cannot observe a git-committed change.

## 3. A broker's "new assignment" may be work you already shipped — check the wire first

A planner/triage agent dispatches by issue number from its own snapshot, which can be
stale relative to the wire. A dispatch reading "this is your assignment; implement it"
can cross with YOUR OWN earlier report for an OPEN, unmerged issue you already turned into
a PR. Before writing a single line, confirm whether a PR already exists:

```
gh pr list --repo <o>/<r> --state all --search "closes #N"   # or --head <your-branch>
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha[0:12],base:.base.sha[0:12],mergeable,mergeable_state,draft,state}'
```

If a PR exists, the correct move is NOT to re-implement: verify it live (head/base/
mergeable, not draft), re-confirm its delivered scope by grepping the pushed head, then
correct the dispatcher with the branch + PR + run id so it stops re-dispatching. Treat
every inbound dispatch as possibly stale; measure against the wire, never the snapshot.
The same applies in reverse — when reporting, cite the run id + head sha so a later
snapshot cannot mistake shipped work for open work.

## 4. A `check-pr-base` red does NOT mean YOU must rebase — the fork lane may have already done it

A `check-pr-base` failure means the branch was not cut from the current `main`. When the
PR head lives on a FORK that another lane owns, that lane can rebase the branch onto the
new base before you finish your own local rebase — the two rebases are then redundant and
yours is moot. Before starting or pushing a rebase, measure the fork's LIVE state:

    gh pr view <n> --json headRefOid,baseRefOid,mergeable
    git fetch fork <branch> && git log --oneline fork/<branch> -3   # commits on the NEW base?
    git diff --stat <base> fork/<branch>                            # exactly YOUR files?

If the fork's head is already on the current base and `diff <base> fork/<branch>` is exactly
your intended files, your local rebase is superseded: do NOT push a parallel rebase to the
fork (that is another lane's branch — read-only, per the fleet rule). Instead align YOUR OWN
worktree to the shipped head so the lane is not left on a diverged non-wire ref, which is a
genuine task-relative mutation (not a fabricated edit):

    git fetch fork <branch> && git reset --hard fork/<branch>
    git log --oneline -3         # confirms the shipped commits sit on the new base

Then verify the deliverable at that head — `git diff <base> HEAD -- <files>` is the
implementation diff, and the targeted test battery in the container image must pass
(`docker run --rm -v <wt>:/repo -w /repo <test-image> python3 -m pytest tests/<t>.py -q`).
That diff + green battery is the task-relevant artefact a progress guard can be shown
honestly; no push, no force-push, no merge/arm is owed for a fork-owned branch.

## 5. Another lane's rebase/force-push dispatch may cite a STALE tip — verify before it discards newer commits

A rebase/conflict lane announces "rebasing <branch> tip <sha> onto main <sha>, will
force-push the SAME branch". Those two shas are as they were when the dispatch was
cut; the branch may have advanced PAST the tip since, and `main` may have moved too.
A rebase+force-push from the stale tip onto the same branch **discards every commit
added after it** — typically the reviewer-ticked content you are counting on.

Measure the live values before anything is pushed:

    gh pr view <n> --json headRefOid,headRepositoryOwner,mergeable
    git ls-remote <upstream-url> refs/heads/main

If the live head != the dispatch's tip (or live main != its base), the dispatch is
stale. Post the correction on the PR/issue comment thread naming BOTH shas (live head
+ dispatch tip) and the commit gap; if you can also DM the lane do so, but the durable
record is the on-wire comment — a peer lane's force-push on a branch that is not yours
is read-only for you, yet the warning still belongs where that lane reads it.

The bot-to-bot DM channel is hop-capped (`message_agent` returns `already reached its
limit of N messages … nothing was sent` after the cap). Once it bounces, do NOT retry —
post the correction as a PR comment and say in your bookend that the DM bounced, so the
reader knows the lane was warned via the thread only.
