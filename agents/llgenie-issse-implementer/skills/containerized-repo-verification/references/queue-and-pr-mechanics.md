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
