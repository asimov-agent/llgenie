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
- **Prove it is safe to push before you do — never infer it from breath.** The branch may be green while a
  run is still `queued` (not yet `in_progress`), and a push at that moment costs exactly that verdict:
  `gh api repos/<o>/<r>/commits/<HEAD>/check-runs --jq '[.check_runs[] |
  select(.status=="in_progress" or .status=="queued")] | length'` → `0` is the only "safe to push". A `1`
  means hold: the run the head has been waiting on would be cancelled by your next push. Measured: #919 hit
  this mid-flight when a remote re-take (`a19ae75c`) landed a commit-and-queue while an unrelated rebase was
  prepared — the rebase moved the local head, and only the probe, run again at the real head, said "hold".
- **But not every `queued` job is the verdict; read the GATE, not the count.** A residual matrix job can sit
  `queued` long after the defining check answered — measured: at a19ae75c the `guard` job was `completed /
  failure` while an orphaned `linux-published / install-published-none` still read `queued`. A single
  `1`-from-any-name would have told you "hold" when the only thing left was a starved job that would never
  produce a verdict anyway. Discriminate: is the run the PR's gate actually waits on (`guard`,
  `check-pr-authors`, `check-agent-profiles`) still open, or is it the residual sim? If the gate concluded
  and only a detached matrix job lingers, the count alone is not "hold" — it is the many-queued-jobs
  mirage the planner calls "a job that never starts and a job cancelled look identical".
- **`BLOCKED` on every PR is a symptom of this, not an approval problem.** The proof is the one PR reading
  `CLEAN` while the rest are blocked: its run happened to get scheduled.
- **A check that reads `cancelled` at an UNMOVED head is a non-verdict — re-run it before believing
green or red.** The concurrency group kills runs at a starved queue, so your own push's gate attempt can
end `cancelled` seconds later precisely because you pushed; treating that as the branch's real answer is
the same mistake as believing a killed batch. `gh run rerun <id>` (or re-arm to re-trigger) restores the
attempt, and only a `completed/success` or `completed/failure` is a verdict worth quoting. Re-read the
probe and the gate conclusion at the head you are about to push, not an earlier run you already answered.
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

## A generated index goes CONFLICTING when `main` adds a row the branch lacks

A long-lived branch on a base that predates a new `docs/changes.d/` fragment reads `MERGEABLE` until the
moment `main` merges that fragment's row; then GitHub re-computes the merge and the PR flips to
`DIRTY`/`CONFLICTING` because the generated `CHANGES.md`/index is a single file both sides rebuilt. The
conflict is not a real code clash — it is two regenerations of one derived file landing in the same region.

- **Diagnosis is one `gh pr view <n> --json mergeable_state`** showing `dirty` with `mergeable=false`
  while `git merge-tree` on your head against your (older) record of `main` reports clean. The reason:
  `origin/main` moved since you cached it, and the new tip added a fragment row. Recheck `git rev-parse
  origin/main` before assuming the conflict is real.
- **The additive, freeze-respecting fix:** do NOT rebase or force-push (a freeze forbids both).
  `git merge origin/main` (a plain merge commit, history-preserving), then resolve `CHANGES.md` by
  regenerating it from the fragment union — `make changes-index` after copying any `agent-wiki/` note the
  new fragment links (the index errors out listing the missing note until you bring it over). Resolving to
  a *union* regenerated from fragments covers both sides; resolving to one side's file drops the other's
  documented rows.
- **Verify the merge really cleared it**: `git merge-tree <base> main <branch>` → zero conflict markers,
  and `gh pr view --json mergeStateStatus` → `BLOCKED` (mergeable), then re-arm. A `BLOCKED` that was
  `CONFLICTING` seconds earlier is the same PR, no longer dirty.
- **Commit the merge, do not squash-dismiss it.** The merge commit is the record that the base moved and
  you absorbed it without rewriting; keep it in the PR's history.

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
- A stacked PR (base != `main`) must **never** be armed: auto-merge on a stacked PR does not sit — it
  MERGES the PR into its non-main base, stranding a merge commit that is an ancestor of neither
  `main` nor the tree head (measured: #954 auto-merged into `feat/agent-profile-implementer-skill` at
  08:27:41Z and its commit is in neither). Report `auto=none (stacked, base is not main)`.

## `gh pr merge --auto` exits 0 when it does nothing — UNLESS the base accepts merges

Arming has **three silent triggers and one active hazard**. The silent ones leave `autoMergeRequest=null`
while the command succeeds: a **draft**, a `do-not-merge` label, and a base whose branch protection
refuses the arm (a stack on a protected/non-main branch). `mergeStateStatus` may read `UNKNOWN`.

The **active hazard** is a stacked PR on an UNPROTECTED non-main branch: `gh pr merge --auto` does not
no-op there — it MERGES the PR into that branch. #954 hit exactly this: armed onto
`feat/agent-profile-implementer-skill`, it auto-merged at 08:27:41Z, and the merge commit is an ancestor
of neither `main` nor the current tree head. `autoMergeRequest` after that is not a lie, it is a merge
you did not intend. So the read-back (`--json autoMergeRequest`) must be a check on **which base** you
armed, not just on whether the arm is present.

- **Read the arm state back; never trust the exit code**: `gh pr view <n> --json autoMergeRequest`. Absent
  → not armed, and say so with the reason (draft / label / non-default protected base).
- **Never arm a PR whose base is not `main`.** A stacked PR's "merge" is a contamination of its base, and
  once it happens the commit is in neither `main` nor the tree — it is orphaned work you cannot review.
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
- **Rebase the WHOLE branch with plain `git rebase <main>`, never `--onto <main> <old-head>`.** `git rebase
  --onto <main> <some-earlier-branch-head>` replays ONLY the commits after that fork point and silently
  DROPS everything before it — the branch shrinks mid-rebase with no error. The pitfall is that `--onto`
  reads as "rebasing from a base" and the disaster looks like a successful rebase that lost most of the
  branch. For "bring my whole branch onto fresh main" the command is `git rebase <main-tip>` (no `--onto`);
  there is no legitimate common case that wants `--onto <main> <an-old-commit-of-my-own-branch>`. If you
  already ran it, `git rebase --abort` and redo — the work is still safe until a push or a `--continue`
  that succeeds.
- **A stacked rebase through a generated-file conflict recurs per commit, so drive the CONTINUE as a loop,
  not a one-shot.** When the branch carries several "regenerate CHANGES.md" commits, each one re-conflicts
  on a rebase off a moved `main`; a single `--continue` stops at the next conflict and you resolve in a
  loop. For each iteration: regenerate the derived file from its fragments (`scripts/changes_index.py
  write`) to a union (never resolve to one side), `git add` the resolved files, then `--continue` — and
  give `--continue` a no-op editor (`GIT_EDITOR=true`), or it blocks opening an editor mid-loop. Set a loop
  bound so a quagmire aborts; 30-40 iterations of regen+continue is a long but bounded rebase, not a hang.
- **A worktree's rebase state lives in the MAIN clone's admin dir, not `worktree/.git/`.** `git rebase
  --continue` timing out mid-rebase leaves `ls .git/rebase-merge` empty (the worktree `.git` is a pointer),
  which reads as "rebase done" when the rebase is paused at the next conflict. Check with
  `git -C . status` for `interactive rebase in progress; onto …` or look under
  `<main-clone>/.git/worktrees/<name>/rebase-merge` before concluding a rebase finished.
- **A PR reads `CONFLICTING`/`DIRTY` right after a force-push, then GitHub recomputes it clean.** Immediately
  after `git push --force-with-lease` of a rebased branch the PR can report `mergeable=CONFLICTING` while the
  merge is actually clean — GitHub re-checks mergeability asynchronously. Do not diagnose or re-rebase on
  that reading; re-read `gh pr view <n> --json mergeable,mergeStateStatus` after ~20-30 s and treat the
  first reading as the recompute, not a verdict. The confirming signal: the base you rebased onto IS current
  `main` (re-fetch and compare `FETCH_HEAD == <base>` same-turn), so a genuine conflict requires `git
  merge-tree <main> HEAD` to show markers — not the PR's transient state.
- **Split a large pytest batch and report exit codes, not counts.** One invocation over ~70 files was killed
  at 16 % by the runner's wall clock (`PYTEST_EXIT=137`, SIGKILL); 36 files per invocation finished clean in
  ~2 min each. Name the 137 as an artifact so nobody reads it as a failure, and prove a remaining red by
  running the same nodes against the exported base — an identical set means environment, not diff.

## A foreign-lane red is that lane's to clear, not yours to "fix" in place

A red in ANOTHER lane's file (a lint failure, a live-longer finding, a gate it owns) is not a free -fix the
moment it blocks your PR. Editing that lane's copy in your tree to clear your own gate does not settle the
red — it MOVES it. Measured: a one-line lint "fix" to a tester-lane SKILL (removing a stray `---`) made
the tree copy diverge from that lane's live profile, which turned `lint` green and flipped
`check-agent-profiles` to a `live-longer` finding (tree 3804 b vs live 3808 b) — strictly worse, and it
touched a protected agent-instruction file that the sync refuses to route around.

- **A red in another lane's file is a message to that lane, not a task for you.** Bookend it (name the
  sha, the offending line, the exact fix), and let the owner take its own tree copy forward — the planner's
  rule "each owner takes its tree copy" — instead of reaching in.
- **A tree-copy edit that diverges from that lane's live is a second, opposite red.** The direction
  guard (refuse to shrink live) exists precisely to catch a unilateral tree edit that lags the live file;
  your "fix" becomes the thing the gate refuses.
- **A count-clean dedupe can still fail the fence.** A lane may offer a dedupe that counts one occurrence
  per rule and drops a retired bullet, yet its retained block paraphrases a canonical rule — so
  `block_in_soul` is still False and taking it imports a gate-red fence. Run the fence comparison even on
  an offer the lane certifies count-clean; refuse when the retained text differs. The occurrence count
  and the bullet total are not the check; the fence is.

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

- **Fetch fresh canonical `main` BEFORE any other work — every job, every time.** Confirm which remote is
  canonical first (`git remote -v`: the repo's own namespace — is `origin` the shared owner or your fork?),
  then `git fetch <canonical> main` and read it back. Never reason from a `main` sha you already had, never
  from one quoted in a chat message (stale by the time you read it), and never from a remote name you
  *assume* exists. In this repo `origin` = `asimov-agent/llgenie` (the canonical) and `fork` = `andyholst`;
  there is NO `upstream` remote — `git fetch upstream main` fails with "repository does not exist", which is
  itself the signal to check the remote list rather than guess.
- **Branch from `<canonical>/main` at the sha you just fetched** — never from a branch you already had.
- **Answer a plan against the current `main`, not a four-heads-old snapshot.** A planner or reviewer who
  measures at an old sha (`4fb3bf3a`) will report "rule 13 twice in your SOUL" or "3 of 4 live-longer
  findings" that a dedupe or a main-merge has already cleared. `git merge-base --is-ancestor <their sha> HEAD`
  tells you in one command whether their premise is behind yours; if it is, re-measure at HEAD and post BOTH
  shas, never a vague "that's old".
- **Re-read the head in the SAME turn you quote it — a sha is a claim about the past the moment another
  lane can push.** Three shas in one status line, all three stale, makes every claim built on them
  backward-looking; it is your own rule ("a rebase preserves content and destroys shas; only the content
  check can tell you") turned around against you. `git ls-remote origin refs/heads/<branch>` is one line
  and is the only honest head to quote. Post the sha you just fetched, not the one you memorised.
- **The base:** `git fetch origin main`, then branch from `origin/main` **at the sha you just fetched** — never
  from a branch you already had, never from a sha quoted in a chat message (stale by the time you read it).
  In this repo `origin` is the canonical same-repo owner, so `git fetch origin main` is correct; in a
  fork-side worktree `origin` is the fork and the canonical apex is a different named remote — always confirm
  the remote list before naming the fetch target.
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

## A PR's head is the REMOTE branch, not a local worktree or scratch ref

A "your branch moved" / "you pushed during the freeze" claim is settled against the remote, never by
looking at local refs. Measured: a lane cited three shas (`e9c7e7f3`, `7e4a8519`, `5e74cb68`) as the #919
head "advancing under a stop" — all three resolved to LOCAL scratch branches (`tmp/retake-myskill`,
`tmp/lint-fix`, `pr944-replay`), never pushed, and the PR's remote head was frozen the whole time.

- **The authoritative read is the remote branch, twice-verified:** `git ls-remote origin refs/heads/<branch>`
  and `gh pr view <n> --json headRefOid` must agree; that sha is the PR's head, and nothing else is.
- **A refname can be AMBIGUOUS and read a stale ref — fetch with an explicit refspec, never `origin/main` by
  a short name.** Measured: `git rev-parse origin/main` returned `6d9fef1d` (an old leftover) instead of the
  real current main, because `origin/main` as a short name resolved to something else than the remote-tracking
  ref. So a base-watch claimed "#919 is ~1 behind" against a STALE sha and I had to correct it with
  `git fetch origin +refs/heads/main:refs/remotes/origin/main` then `git rev-parse refs/remotes/origin/main`
  (238dcd2c — which #919 already contained). The fresh-main rule is: fetch an explicit
  `+refs/heads/main:refs/remotes/origin/main` and read `refs/remotes/origin/main`, so the refname cannot
  quietly resolve to the wrong sha.
- **A disputed sha's membership is `git merge-base --is-ancestor <sha> origin/<branch>` — one command for
  "is it actually on the branch".** If it is not an ancestor, the sha is on another ref (or only local);
  say which refs contain it (`git for-each-ref --contains <sha>`), and stop.
- **`tmp/` and `pr<N>-*` worktrees are local, disposable, and NOT the PR's history.** A worktree checks out a
  branch for a moment's work; its HEAD is not evidence about what was pushed. Distinguish "carries that
  content locally" from "advanced the remote PR" — the objection only bites the latter.
- **Concede a mistaken "your branch moved" flag on the record with the two reads as proof, then drop the
  item** — measure-then-escalate holds against an accusation about your own lane as much as against a planner
  premise. Do not argue; show `ls-remote` + `merge-base` + `headRefOid`.

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

## The author allowlist bans a display name `main` itself carries — measure, then escalate, never rewrite

Measured on `#919`: `check-pr-authors` failed on 11 branch commits, but **none of them was mine** — I author
`Andy Holst <andy.holst@protonmail.com>`, which the gate accepts. The failures were commits landed as
`Andy <andy.holst@protonmail.com>` (the owner's actual git config authors "Andy"), plus one with a typo'd
domain `andy.holtd@protonmail.com`.

Re-measured at head `63aa93c1` the count is 14 — the same two classes plus a third: commits landed as
`Andy <andy.holst@protonmail.com>` (the owner's git config authors "Andy"), one with a typo'd domain
`andy.holtd@protonmail.com`, and two squashes of the stacked PRs #972/#978 carrying `Co-authored-by:
LLGenie Architect <architect@llgenie.local>` (a local fake domain). After a rebase onto a newer main the
count fell to **11 at `e3b8014c`** — every subsequent rebase re-measures the range, because a squash copy
already reachable from the new base is no longer this PR's addition (`b6d9cfd8` #981, "patch contents
already upstream", was dropped and its finding went with it). Re-verified at `6c198627` the count holds at
**11** — a snapshot earned by re-measuring, not by trusting the earlier head's number. The two co-author
trailers survive every rebase and no `--reset-author` clears them. So a stated count is a snapshot of a
head, not a constant:
**re-measure at the CURRENT head before asserting the gate's red size.** All are the scanner's own commit
range — the static producer half stays clean.

Two separate facts, two different responses:

- **A typo is yours to fix only if the commit is yours**, and re-authoring a mid-history commit rewrites
  every sha after it, which strands every stacked PR (base = your branch) — a *conversation first*, and a
  rewrite of a branch another lane is working on is not unilateral (rule 14).
- **The allowlist accepts `Andy Holst` / `Asimov Agent`, yet 33 of the last 40 commits on `main` are authored
  `Andy <andy.holst@protonmail.com>` — same email, different name.** A gate that bans the identity the
  branch's own history uses can never pass a branch that pulls `main` in, and re-authoring does not stop the
  next occurrence. The stable key is the email; the display name is not. That is a policy change in the
  gate's own allowlist, not a branch fix.

So: verify which failures are yours (`scripts/check_pr_authors.py report --base <main> --head HEAD`),
expect your own to be `OK`, and escalate the rest with the two measurements — a typo fix that needs a
rewrite, and an allowlist that contradicts `main`'s own authors.

A re-author instruction can itself be built on a stale head and a partial count. Measured on `#919`: a
dispatcher, having earlier ruled "do NOT rewrite the author, fix is email-matching (#840)", later ordered a
re-author of "three squash authors" measured at an old tip (`80f54f9f~3`) while the real tip had moved
twice (to `5baca03a`, where the gate is red on **14** findings, not 3 — 12 `Andy <…>` squashes plus two
`Co-authored-by: … architect@llgenie.local` trailers that no `--reset-author` can ever clear). Declining
was correct: a rewrite of three shas leaves eleven findings and a still-red gate, and it rewrites shas
under every stacked PR (base = your branch) for a field that is cosmetic. So the check list grows by one:
**before taking a re-author order, re-measure the failure count at the CURRENT head and confirm the
instruction raises the earlier no-rewrite ruling — escalate a contradiction rather than force-push a
history rewrite that cannot clear the gate and that the gate's own durable fix (email-matching) removes
by construction.**

## Changing a gate's comparison key: enumerate every consumer, and make the tests the evidence

When a gate rejects the very identities its own branch carries (a permitted person under an alias name),
the fix is to change WHAT the gate compares on — the stable email instead of the display name — not to
rewrite history. That key change has four hard edges, each of which bit in sequence.

- **The self-gating caveat: the gate runs its own script from the PR's own tree, so the loosened check
  passes its own `guard` trivially.** A gate that keys on email will approve the PR that just keyed on
  email. That is not evidence the change is right — **the TESTS are the evidence, not the green self-run**,
  and the PR body must quote the pytest output. A reviewer who sees only "guard: pass" cannot tell whether
  the gate loosened by design or was hollowed out.
- **Changing a dict's KEY semantics ripples to every consumer, not just the "main" check.** Grep the symbol
  (`ALLOWED`, `grep -n ALLOWED`) across the whole module AND its sibling seam — name→email meant
  `ALLOWED[name]`-style lookups in the co-author evidence, the producer scan, the seam's `identity()`/`
  allowed_note()`/`report()`, and every test that read the old shape. A test that still does
  `ALLOWED.get(name) == email` reimplements the old contract and fails on a shard you did not run.
- **A fixed pair check re-bites one level up.** Closing the cross-identity gap in `check_producers` but
  leaving `check_seam.pins_identity` on `any(name allowed) and any(email allowed)` re-introduces the same
  bug in the other consumer of the same identity. When you fix a comparison-key bug, grep the WHOLE file
  for every place that used the old semantic (independent `name in` / `email in`), including the commodity
  helper the seam reuses, and fix them symmetrically.
- **A name×email cross-product pair check false-flags a producer that legitimately pins two full
  identities.** Pair-checking by iterating every (name, email) reports A-name/B-email and B-name/A-email
  "mixed pairs" that never co-occur. Fire the pair finding only when the file has NO valid pair at all;
  a multi-identity producer passes, a genuinely mixed one still reds.

Each of the four gets a negative control: loosen the check and the pinning test must fail before it passes.

The durable-fix framing when the gate contradicts its own history: an alias list is NAMES only — an allowed
name at the wrong email still fails, so a typo'd-domain commit stays a violation even after the email-keying
fix. The stable key is the email; the display name is a spelling the squash writes from the profile.

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

## Rebase only when the branch is CONFLICTING, never on every `main` move

An armed branch does not need to chase `main`. `main` advances constantly while a PR sits upstream, and
a rebase on every move is churn that rewrites shas under every stacked child and forfeits the arm's
verdict. The owner correction: **rebase only when the PR is actually `CONFLICTING`, or its base merges**;
a branch that is `MERGEABLE` but slightly behind is not broken. Before touching it, verify the trigger —
`gh pr view <n> --json mergeable` → `MERGEABLE` means leave it armed and report, `CONFLICTING` means
rebase. This is the flip side of the older "rebase the whole branch onto fresh main" rule: that rule is
for when a rebase is actually owed, this one says a behind-but-clean branch is not a reason to rebase.

## Rebasing a stacked child onto a moved parent — the `--onto` three-argument form

To move a stacked PR's *own commits* on top of a parent that has advanced, the rebase needs the upstream
explicit — and the branch's own tip is the wrong upstream-argument (measured: the author moved #1008's
branch to `bae12f54`, the parent tip, silently dropping the dedupe commit, because
`git rebase --onto <new-tip> <own-remote-tip>` has an empty `<old-tip>..HEAD` range and just relocates the
branch):
```bash
# WRONG: upstream = the branch's own remote tip -> empty range -> branch MOVES to the new tip, commit lost
git rebase --onto <new-parent-tip> <own-branch-remote>     # BAD
# RIGHT: upstream = the OLD parent tip the commit currently sits on -> replays only the child's commit
git rebase --onto <new-parent-tip> <old-parent-tip>        # replay just the child commit
```
Recover from the mistake before pushing: the dropped commit still exists (`git cat-file -t <sha>`),
`git reset --hard <sha>` puts the branch back, then re-run with the correct upstream. Verify the child is a
descendant of the new parent tip before force-pushing: `git merge-base --is-ancestor origin/<parent> HEAD`
must be true.

**A stacked child rebased onto a moved parent can conflict on ANOTHER lane's SOUL, and the resolution must
keep BOTH the lane's new content and your scoped edit.** When the parent advances with a commit that touched
a lane's `SOUL.md` (its own new rule bullet) in the same own-rules section your child edits (a dedupe), the
rebase across it conflicts there. Resolve by taking the PARENT's version of the file (the other lane's bullet
is correctly placed) and re-applying ONLY your scoped change — never "keep either side" wholesale, and never
let the dedupe side drop the other lane's new bullet (measured: the dedupe-side resolution silently removed
a lane's monitoring bullet). After resolving, verify BOTH properties survive: the other lane's new content
present (`grep -c "<its bullet>"` = 1) AND your dedupe applied (`_duplicate_rule_debts` on that lane is
`[]`), then re-check every SOUL's `block_in_soul` — a bullet placed inside the canonical fence instead of
the own-rules section breaks the byte-identical compare (6820 b vs 5842 b). Amend the corrected file into the
child commit and force-push to finish.

## Two vehicles for one gate fix land the same line on ONE, never both (the #824 collision shape)

When two open PRs fix the same gate (`#993` fix/840-email-author-gate vs `#977` fix/971-author-alias, both
email-keyed author allowlists), a follow-on line each is owed (here: `"architect@llgenie.local":
frozenset({"LLGenie Architect"}),` because `Co-authored-by: LLGenie Architect <architect@llgenie.local>`
trailers in `73cbe680`/`5999f9ad` are in neither ALIASES set) has a merging-order hazard: it must land on
the vehicle that WINS the consolidation, never on both — landing it on both is how `#824` became a
three-branch collision. Before pushing the line, confirm which vehicle survives (`gh pr view <n> --json
state,mergedAt` for both), and if the winner is unresolved, hold the line as a comment on each candidate
with the evidence, not a push to either. Measure the gate's own `ALIASES`/`ALLOWED` symbol before claiming
a co-author is covered — `grep -n "architect" scripts/check_pr_authors.py` (measured: neither ALIASES set
contained `architect@llgenie.local`, so an email-keyed gate still rejected both commits).
