# Queue mechanics, suite reproducibility, and a PR's blockers

Depth moved out of SKILL.md so the always-on rules stay short. Each section is a measured
failure mode from a live repo; the commands are the evidence, not illustrations.

## A suite result without its environment is not reproducible

**When two runs of the same tree disagree, compare the environment before the code.** Measured: the same
commit gave `14,547 passed / 0 FAILED` in one container and `14,568 passed / 6 failed` in another; the
difference was `HF_TOKEN`/`GITHUB_TOKEN`/`GH_TOKEN` being present in the second, and the 21-test gap was
the fingerprint of tests that skipped early or took a credential branch. Record the env vars beside the
count, or the number cannot be reproduced by anyone else.

**And a full suite on a stale base measures the base, not the change.** Two 1h30 full runs were spent on
a branch whose base predated the commit that fixed six assertions — both were guaranteed red and neither
said anything about the change. Before any full run: `git merge-base --is-ancestor origin/main HEAD`, and
run on the rebased head. If the base is behind, the honest report is "the base is red", not "the change
failed".

## `cancel-in-progress: false` does NOT protect a pending run

A starved `workflow_run` sweeper that "never runs" is usually this, not a slow queue. GitHub keeps **one
running plus one pending** run per concurrency group, and **a newly queued run cancels the pending one**
regardless of `cancel-in-progress` — that flag only protects the run already executing. So a workflow
triggered per upstream completion, grouped per branch, kills its own backlog: runs end `cancelled` with
**no job rows at all**, and the depth never drains.

```
on:  workflow_run: {workflows: ["CI"], types: [completed]}   # one trigger per CI completion
concurrency: {group: auto-merge-${{ head_branch }}, cancel-in-progress: false}
→ last 25 runs: 16 cancelled · 9 queued — nothing completes
```

**The fix for an idempotent, stateless sweeper is ONE repo-wide group that supersedes:**

```yaml
concurrency:
  group: auto-merge          # not per-branch: the sweep decides for itself what to do
  cancel-in-progress: true   # newest replaces older, running or pending
```

Safe there and not in general, for three reasons worth stating when proposing it: the sweep holds no
state between runs, each merge is a single atomic `gh pr merge` call (a cancel lands before or after one,
never inside), and two sweeps racing on the same PR is the failure being prevented. Also note a `schedule`
trigger collapses into the same empty-branch group, so cron sweeps already share one group by accident.

Separately: **a job with no `timeout-minutes` while its siblings carry 45–240 can hang forever** — the
same class as a sweeper that reports success without running.

## A push into a branch whose run is still `queued` is a cancellation, not an iteration

`cancel-in-progress: true` on `pull_request` is meant to keep the newest commit's run and kill older ones,
which predicts **one survivor per push series**: cancellations ≈ pushes − 1, and one success per branch.
When the observed shape is instead **3 successes in 100 runs**, the cause is not the flag — it is **queue
depth**: runs die while still `queued`, because the next push arrives before GitHub ever schedules them.

- **The flag is benign at a queue of minutes and destructive at a queue of hours.** The lever is depth
  (fewer concurrent runs, more runners), not the flag, and the two must not be "fixed" together.
- **A run only produces a verdict if the head stops moving for longer than the queue takes** — so push
  once, then FREEZE the branch. Iterating on a queued branch cancels the run that would have answered.
- **`BLOCKED` on every PR is a symptom of this, not an approval problem.** The proof is the one PR reading
  `CLEAN` while the rest are blocked: its run happened to get scheduled.
- Falsifiable check after any relief: successes should match the number of branches that stopped being
  pushed. If the cancelled share stays above ~80 % with hours-long `queued` times, the queue is still the
  constraint.

## `git diff A B` answers "what differs", not "what the branch added"

Two-dot `git diff A B` prints what **B has and A lacks** — so a `--stat` against another branch's tip shows
*that* tip's additions, and reading it as "branch A edits this file" inverts the result. Measured in
llgenie: `git diff --stat cd0ea71 870c915 -- .github/workflows/auto-merge.yml` → `44 insertions(+)`, which
is #918's work, not the other branch's; the three-dot form against the merge base settles it:

```
git diff --name-only origin/main...cd0ea71     # what the branch actually adds
  CHANGES.md · agent-wiki/… · docs/BOTS.md · tests/test_auto_merge.py · tests/test_bot_pipeline_isolation.py
                                                # no workflow file at all
```

Use `A...B` (three dots, merge-base) for "what does this branch change", and `git merge-tree` for "do these
two land together" — never a two-dot diff, and never by eye.

## `gh pr list` matches TITLES; `--head` answers "does this branch have a PR"

A branch whose PR title does not contain the branch's own subject reads as orphaned under
`gh pr list | grep <subject>` — and "orphaned" invites deleting live work. Measured: `ci/874-auto-merge-guard`
looked PR-less by title-grep and had **#886** open, `MERGEABLE`, since hours earlier. The lookup is
`gh pr list --head <branch> --state all`; a branch without a *matching title* is not a branch without a PR.

## A union of two insertions can be parseable and still be bisected

Resolving a conflict by keeping both sides has two failure modes, and only the first is loud:

- **Loud:** the sides sit inside one function, so "keep both" yields `IndentationError: unexpected indent`.
  Six conflicts in one file (an `add_argument`, a docstring body, a dict literal) measured this way — the
  parse error is the *proof* the conflicts are not additive, not a style objection.
- **Silent, and worse:** the union lands two halves of one function body such that the file still parses,
  but a branch of the function is gone — measured in llgenie, a merged gate returned `None` from a function
  that should return a list, and died only when something called it (`TypeError: 'NoneType' object is not
  iterable`). No red at merge time, no red at import time.

So after any hand-resolved union of code: **diff the merged function against both parents**
(`git diff <parent> <merge> -- <file>`) and run the tests that exercise it — a green gate is not evidence the
function survived, because the gate may be the thing that was bisected. Also `grep -c "<def name>"` for each
side's key symbol, and **prefer the stricter side outright when both implement one check at different
strengths** (a content test beats a size test; keeping both is two implementations of one rule).

Related: an assertion that pins an exact set (seven names, a count) reds on the next legitimate addition —
assert a **subset** of the guarantee you need, or the gate gets disabled by the first correct change.

## A closed PR's number stays readable and looks like a live dependency

Parked work held "until #N merges" can be held behind a **closed** PR for hours: the number renders
identically in a comment and in a search result, so nothing about it reads as dead. Measured: a lane kept
a delta parked behind a superseded PR while its replacement sat open and armed.

- Before sequencing behind any PR: `gh pr view <n> --json state,mergedAt`. `state=CLOSED` with
  `mergedAt=null` means the work landed nowhere and the dependency is imaginary.
- **A superseded PR keeps its head sha.** Quote the *branch tip* (`gh pr view <n> --json headRefOid`) or
  the command, never a sha from a message — including your own. A reader who verifies an unreachable sha
  gets `not a valid object name` and cannot tell whether the work exists at all.

## Arm when the work is done, not when it is approved (owner directive 2026-10-29)

"Done" — the last push, the last check on a finished PR — triggers the arm, and the arm is a hand-over to
the merger, not a merge. A finished, UNARMED PR is invisible to every merger sweep and waits for a human to
notice it; that is the failure the directive removes.

- The arm command is `gh pr merge <n> --squash --auto`, and it is run when the work is finished — not left
  to "when a reviewer approves". Read the arm state back in the SAME comment and report the arm time:
  `gh pr view <n> --json autoMergeRequest` — `--auto` exits 0 and arms NOTHING when the base is not the
  default branch, so the exit code is never the fact (issue #964).
- **The only accepted reason a finished PR sits unarmed** is an owner instruction not to merge it; then the
  comment says `auto=none (owner instruction)` and where that instruction lives. Anything else — a draft, a
  missing reviewer, "I will wait a bit" — is the failure, not an excuse, and the report names which of the
  three silent triggers it was.
- A stacked PR (base != `main`) cannot be armed, so name that too rather than reporting a false arm.

## `gh pr merge --auto` exits 0 when it does nothing

Arming has three silent-failure triggers, all of which leave `autoMergeRequest=null` while the command
succeeds: a **draft**, a `do-not-merge` label, and a **base that is not the default branch** (a PR stacked
on another branch has nothing to merge into). `mergeStateStatus` may read `UNKNOWN` for the same reason.

- **Read the arm state back; never trust the exit code**: `gh pr view <n> --json autoMergeRequest`. Absent
  → not armed, and say so with the reason (draft / label / non-default base).
- **`mergedAt` is not evidence of an arm.** A PR can land by an owner's or a sweep's merge after a failed
  arm, so a post-hoc look at `mergedAt` confirms a merge that your command never enabled.

## Re-cutting a fork-head PR as same-repo

A fork `pull_request` run gets a read-only token and **no repo secrets**, and the approving identity has to
be a second one — so a fork-head PR can sit green and unmergeable while the same commits on a same-repo
branch would land. Re-cutting is cheaper than diagnosing it, and it is not a rebase:

```
git push origin HEAD:refs/heads/<branch>              # same repo, same commits
gh pr create --repo <owner>/<repo> --base main \
  --head <owner>:<branch> --body-file /tmp/body.md
gh pr merge <new> --squash --auto                     # then READ IT BACK: autoMergeRequest
gh pr comment <old> --body-file /tmp/comparison.md    # head sha, why, re-runnable verification
gh pr close <old>
```

- **`--head <owner>:<branch>` is what makes it same-repo** — leaving the prefix off is the silent default
  that reproduces the defect.
- **Close the old PR; do not force-push the fork branch.** Its head sha and history stay readable, which is
  what lets a reader compare the two.
- **Do not re-cut to fix a different symptom.** A queue-bound PR looks identical from the outside, so measure
  first (`gh api repos/<owner>/<repo>/collaborators/<identity>/permission`, `gh pr checks <n>`): re-cutting a
  PR that was merely waiting throws away the run it was waiting for.

## Rebasing a long-lived branch: the base moved, so the measurements did

An old branch against a moving `main` makes the rebase mechanical and the **recounts** the actual work.

- **Measure the base without mutating your own worktree.** `git archive <base-sha> | tar -x -C $SCRATCH`,
  then run the branch's own checker against that export (`python3 <branch>/scripts/<checker>.py --root
  $SCRATCH report`). The tempting shortcut — stash, `git checkout <sha> -- .`, then restore — silently
  reverts your own working-tree fixes when the restore path is wrong, and it still looks clean afterwards.
- **A ratchet/baseline recorded at the branch's original cut goes red because the BASE grew**, not because
  the branch regressed: other lanes added offenders while it sat conflicting (measured: 34/14 recorded, base
  107/151, branch 22/44). Re-measure both sides, re-record the baseline at the counts the *branch* produces,
  and say why in the commit — keeping the old number makes the guard red on the untouched base, which no
  reviewer can merge.
- **Re-run the docs/index gates: conventions move under you.** A hand-edited index row may now be a per-file
  fragment, and a merged section needs a blank line before its heading — the "keep both" union of two doc
  additions glues a heading onto the paragraph above it, so lint fails on the JOIN and neither side is wrong.
- **Write commit messages to a file and use `-F`.** `git commit -m "…`main`…"` runs the backticks as command
  substitution: bash prints `command not found` and the message lands with words missing. Check
  `git log -1 --format=%s` before pushing.
- **Split a large pytest batch and report exit codes, not counts.** One invocation over ~70 files was killed
  at 16 % by the runner's wall clock (`PYTEST_EXIT=137`, SIGKILL); 36 files per invocation finished clean in
  ~2 min each. Name the 137 as an artifact so nobody reads it as a failure, and prove a remaining red by
  running the same nodes against the exported base — an identical set means environment, not diff.

## A hold is a debt with a named creditor, or it is abandonment

`do-not-merge` means *there is a concrete defect with a tracked fix* — never "this lane would rather not".
`mergeStateStatus` reads `BLOCKED` for both a real defect and a forgotten tag, so the label cannot carry
its own reason: **the comment is the record, or there is none.**

The sequence, in order, and every step is somebody's action rather than a state:

1. **Is it totally wrong, or genuinely conflicting with something?** If neither, it is a review — say what
   is wrong in a review comment and leave the label off. "I am not confident" is not a reason.
2. **File the issue that makes the tag removable** — the fix, not the complaint.
3. **Name it in a PR comment**, with the exact condition for removal: `held on #NNN; removed when <X> lands`.
   No issue number ⇒ no tag.
4. **Remove the tag yourself when that issue lands**, and say so with the sha or run id that proves it.
5. **Close the issue.** A held tag with a merged fix is the same defect from the other end: the board shows
   a blocker nobody can clear.

Two corollaries worth acting on:

- **Re-audit every hold each pass.** Tag + no linked issue = either file one now or drop the tag, and say
  which. A hold whose reason expired outlives its author and hides finished work behind a `BLOCKED` row.
- **A merged PR still carrying the label is noise, and the label wins arguments it should not.** Remove it on
  the way out; a merged PR has no state left for a hold to describe.

## Before the first edit: claim, re-read, message the lane, record the conclusion

Two lanes on one branch is not a merge problem — it is an **information** problem, and every instance of it
tonight looked the same from inside: a head sha quoted from a message, a force-push over a tick's briefing,
two lanes calling the same PR `CONFLICTING` while a third held its worktree.

1. **Claim first, in the place the work lives** — a comment on the issue or PR naming what you are taking,
   the branch, the head sha you are starting from, and what "done" means. A DM is not a claim and private
   memory is not a claim: the next reader has neither.
2. **Re-read the thread before your first edit.** An existing claim, a live branch, or a note from the lane
   that touched the files last outranks your plan — including when your plan is better.
3. **Message the overlapping lane directly** with the id, the sha and the specific ask, then **post the
   conclusion in the issue**. A decision that exists only in a DM does not exist for the next reader, which
   is how the same question gets re-litigated an hour later by a lane that never saw it.
4. **Rebase, rewrite or force-push is a conversation first, a command second** — especially on a branch
   another lane is actively rebasing. Say "I am on `<sha>` and will push once" and let them schedule; the
   alternative is a green discarded twice, which is worse than a slow merge.

The failure signature to recognise: **you are about to push and you do not know whether someone else is
behind you.** That is the moment the claim comment was for, and it costs one command:
`gh pr view <n> --json headRefOid` before, and the new sha posted after.

## Bookend the work, and start from a freshly fetched main (fleet rule 15)

An unbookended job and a stale base are the same defect from two directions: the first makes it impossible
to tell who owes a finish comment, the second makes a lane act on a premise someone already invalidated.

- **The base:** `git fetch origin main`, then branch from `origin/main` **at the sha you just fetched** — never
  from a branch you already had, never from a sha quoted in a chat message (stale by the time you read it).
  In this repo `origin` is a fork and upstream is `asimov-agent/llgenie`, so a bare `origin` cannot be the
  canonical source; `git fetch origin main` against the fork is the trap, and the fix is naming the canonical
  remote (`upstream main` here, or the same-repo `origin` when the fork is not involved).
- **Stacked exception:** when the base must be another open PR (the files exist only on that branch), branch
  from that PR's tip and name BOTH shas — the stack head and the `origin/main` you fetched — so a reader can
  tell which part is stacked and which is upstream.
- **Start comment** (before the first edit): issue/PR id, branch, the main sha you branched from, and what
  "done" means.
- **Finish comment** (after the last push): new head sha, what changed, the run id or command that proves it,
  and anything left open. Report the same two lines to the planner.
- **A start with no finish is an abandoned claim; a finish with no start has no baseline to compare against.**

Measured in this repo: a branch sat at `798cbee` while main moved to `5017128e`; the rebase then found a
ratchet baseline recorded at 34/14 that main measures at 107/151, a hand-edited index row that #943 replaced
with per-file fragments, and a lint rule that did not exist at cut — three findings whose only cause was
starting on a base that had already moved.

## A MERGED PR keeps its flags, and that is how a re-cut gets authorised by mistake

Measured: `#847` merged at 08:36:01Z; thirty-four minutes later a briefing still described it as
"`cross=true` · `DIRTY` · the rebase does not resolve it" and authorised a re-cut. Every one of those
statements was true of the **object** and false of the **branch**: a merged PR keeps its head ref, its fork
status and a readable `mergeStateStatus`, and its head is simply an older tree.

```
gh pr view <n> --json state,mergedAt,mergeCommit        # BEFORE planning work against it
git merge-base --is-ancestor <merge_commit> origin/main # is the content actually on main?
git diff --stat <head> origin/main | tail -1            # a re-cut here would only DELETE work
```

The measured shape of that trap: `git diff --stat 5ca8a705 origin/main` → **312 files, 4,869 deletions** —
re-cutting would have produced a PR whose only effect was removing five thousand lines. **A branch that is
behind main is not a branch that needs re-cutting; it is a branch whose work already landed.**

Two corollaries: `DIRTY`/`CONFLICTING` on an old head is a statement about that head, not a verdict on the
change; and the fix for a fork head is a re-cut — but only after `state,MERGED` proves there is something
left to re-cut.

## A PR's blockers are three commands, not a rule of thumb

"Fork head therefore unapprovable" and "`cross=true` therefore can't be armed" are **inferences**, and
both were wrong on a repo where the bot identity holds `admin`. Measure before asserting a blocker:

```
gh api repos/<owner>/<repo>/collaborators/<identity>/permission   # can it approve at all?
gh pr view <n> --json state,isCrossRepository,autoMergeRequest,reviewDecision,mergeStateStatus
gh pr checks <n>                                                # queued vs fail vs pending
```

`isCrossRepository` is a property of the **PR**, fixed at creation and retained after close — it is not a
property of the branch, and it does not change when the same commits are pushed elsewhere. "Is this head
approvable" is `state=OPEN` **and** the permission query; a closed PR answering `cross=true` says nothing
about the branch that now carries its commits.

A PR with `autoMergeRequest` set and one `queued` check is **waiting on the queue**, which is not the same
as blocked by its head's location, and neither is the same as blocked by review policy.
