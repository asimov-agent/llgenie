# Push and rerun discipline

Moved out of SKILL.md when it crossed skill_manage's ~100,000-character cap, which made the file
un-patchable and silently sent every new lesson to the duplicate profile copy instead (#1060). The text is
verbatim; SKILL.md keeps the headings and a pointer so a reader still finds the rule where it is used.

## 3c. A starved runner queue is a finding, not a reason to push harder

Before dispatching, count `gh run list --repo <o>/<r> --limit 40 --json status` by `queued` versus `in_progress`.
Many queued with none running means the platform is not scheduling: every extra `workflow_dispatch` lengthens the
queue without starting anything. Do the blocking fix through the host implementer instead (a rebase, a one-line
guard) and hold further CI dispatches until it drains. “Queued” is never “red” — say so in the brief, or an
implementer will chase a phantom failure.

**Distinguish a stuck queue from a churning one by the age of the oldest queued run.** Queue length alone says nothing:
43 queued with the oldest created minutes ago is a backlog being consumed while new runs arrive (one runner against
many PRs, every push adding one); 43 queued with the oldest hours old is a queue nothing is draining. Read the count
beside `gh api '.../runs?status=queued&per_page=3' --jq '.workflow_runs[0].created_at'` and beside `status=in_progress`,
then diagnose: churn is fixed by fewer triggers per PR (sha-keyed `concurrency`), a stuck queue by finding the runs
holding the runners — often matrices for **already-merged** PRs, whose verdicts nobody will read.

**A job queued on a label no runner matches never concludes — and that reads as "blocked on review".** Count queue length and you will blame pressure; read the job's `runs-on` and you find the real cause. The repo ships the instrument (`scripts/queued_run_alarm.py`), and its output names the mechanism: every stalled job carries the same label, GitHub does not fail a job whose label matches nothing, so the run never concludes and every PR's checks stay pending.

```bash
python3 scripts/queued_run_alarm.py --repo <o>/<r> --minutes 30   # prints label + age per stuck job
gh api repos/<o>/<r>/actions/runs?status=queued --jq '.workflow_runs[]|"\(.id) \(.head_sha[0:8]) \(.created_at)"'
```

Two consequences. **A PR whose every remaining job is that label is complete, not unfinished** — say "supply-limited, 0 failures" rather than "waiting on review", or the owner reads a verdict problem into a capacity problem. And **prove the cause before proposing the fix**: change ONE row to a neighbouring label on a scratch branch and record whether the job picks up (picks up ⇒ the label is not provisionable on this account's plan; still queues ⇒ capacity/billing, which is the owner's to fix and no workflow edit will clear). **Carry a control leg in the same probe run** — a cheap `ubuntu-latest` job beside the suspect labels. Without it, "all suspect labels queued" cannot distinguish a broken workflow from starved labels; with it, a control that finishes in seconds while the suspects queue for minutes settles the question in one run, and a probe whose suspect leg merely queues for "about the normal lag" proves nothing either way. Delete the probe afterwards: it is evidence, not a PR. Run this in a *separate* lane from the queue-clearing: cancelling runs and pausing schedules cannot conjure a runner, which is why a sweep earlier in the evening frees nothing.

**Two matrices competing for one runner pool is one matrix.** Before letting a lane open a new PR (or push a fresh
branch) while another verdict run is live, count what is already running: a 27-job matrix queued behind a 25-job matrix
means the second verdict arrives after the first, and the first is the one the board is waiting on. Hold the new PR,
say the release condition out loud ("open it the moment <run id> concludes, green or red"), and prefer making that
condition self-executing — a watcher on the run id — over a promise to remember. The same arithmetic applies to
dispatching probes: a probe that cannot answer its question until another change merges should wait, not compete.

How to read what CI is actually saying — check-run conclusions, `mergeStateStatus` versus "all checks green",
queue-age diagnosis, and how to run a cancel campaign without killing the runs you meant to keep — is in
`references/ci-state-and-queue.md`. Three rules from it are always-on:

- **`gh pr checks`'s "fail" column is not a failure count.** Only `check-runs` conclusions are: `success`, `failure`,
  `cancelled`. `cancelled` means *not yet* — a newer run superseded it (`cancel-in-progress` on PRs), so the PR has no
  verdict and needs one fresh completed run. Use `gh pr view <n> --json statusCheckRollup` and count the conclusions.
- **"All checks green" is not "mergeable".** Auto-merge gates on `mergeStateStatus == CLEAN`, not on check names;
  `BLOCKED` + `REVIEW_REQUIRED` means the checks passed and a human approval is outstanding — a different sentence for
  the owner than "not ready".
- **`BLOCKED` cannot tell you whether a check was enforcing.** Where `REVIEW_REQUIRED` is on for every PR, that state
  masks `UNSTABLE`, so a PR with a failing check and one with none read identically (`BLOCKED` both). A probe that
  plants a failure and observes `BLOCKED` therefore proves nothing about checks. **`UNSTABLE` is just as blind in the
  other direction:** a PR with eight checks still running and **zero failures** reads `UNSTABLE`, so the value
  cannot distinguish "a non-required check failed" from "checks have not finished" either. Four states, three of them
  collapsing to "not mergeable": failed check → `UNSTABLE`; still running → `UNSTABLE`; review required → `BLOCKED`;
  green + approved → `CLEAN`. Record `reviewDecision` and `isDraft`
  **beside** `mergeStateStatus`, take a before/after pair on the same PR, and treat "advisory vs blocking" as
  answerable only by the merge decision (`auto_merge.decide()` refusing on `!= CLEAN`), not by the badge.
- **Check whether the repo has required status checks before designing a gate contract.**
  `gh api repos/<o>/<r>/branches/main/protection` (404 = none) and `gh api repos/<o>/<r>/rulesets/<id> --jq '[.rules[].type]'`.
  A "skipped class deadlocks branch protection" premise is wrong on a repo with no required checks; the surviving risk
  is legibility — a skipped stage nobody can see afterwards — and the fix is an always-running scope report, not a
  required-check redesign.

## Rerun never re-push; a PR under review is frozen
A run that ended `cancelled` at a head with no successor is repaired with `gh run rerun <id>` (same sha, no new commit). Pushing again cancels the rerun too and burns a whole matrix; each force-push on a queued PR costs ~25 jobs and discards any successes already paid for. Never cancel a run that is mid-flight and two-thirds green just to rebase — let it complete and report the verdict at that head first.

**A rerun is only permitted on a completed run.** While a run is in flight, both forms refuse:

```
gh run rerun <id>                                    # "cannot be rerun; This workflow is already running"
gh api -X POST .../runs/<id>/rerun                   # 403 {"message":"This workflow is already running"}
```

So for a *hung* in-flight run the only lever is `cancel` — which destroys its successes — and "just rerun it" is not an available action. Distinguish hung from slow by the step timestamps: four steps finishing in 27 seconds followed by 50 minutes inside one step with no transition is hung, and the honest report says so with both numbers. **Check `gh pr view <n> --json state,mergedAt` before any rerun or cancel** — a merged PR's run is history, not work, and rerunning it spends a matrix to prove something nobody will read. The durable fix is the deadline: a job with no `timeout-minutes` inherits the platform default (six hours on GitHub), so "hung" and "slow" stay indistinguishable and a held runner is invisible. File the timeout gap as its own issue; do not try to schedule around it.

**A caller's ceiling must exceed the longest job it calls, and the relation needs a test in both directions.** Adding a
`timeout-minutes` to a reusable-workflow caller is the easy half; a caller ceiling *tighter* than its callee kills a
healthy job mid-step and looks exactly like a legitimate timeout, while a callee with no ceiling at all makes the caller's
number meaningless (a six-hour default behind a 60-minute caller). Set the caller above its slowest callee, and pin the
relation (`caller.timeout > max(callee.timeout)`) so the next person who raises a job remembers the caller. A job that
has never completed in the sample gets no ceiling from observation — say so and derive the bound from the closest
analogue instead of inventing a number.

**The fix landing and the freeze are one event.** With `concurrency: group: <workflow>-<ref>` and `cancel-in-progress: true` on `pull_request`, the next push to the same PR always wins: a run can sit ten jobs green with the deciding job eight minutes into its suite, and a three-line push kills it. So a fix followed by a cosmetic push buys a cancellation, not a verdict. When a lane pushes while a run is live, name the cost with the timeline (`started 17:06:58 → push 17:10:10 → cancelled 8m44s in`) and restate the rule as one event — **the fix and the freeze go together, nothing rides along.**

So **a PR under review gets no cosmetic pushes**: batch review feedback into one push after the current verdict lands, and put text-only changes in a comment. When a bot amends a PR repeatedly, the honest diagnosis is not "CI is broken" — it is that the head moved before any run could finish, so no run will ever be cited. State that, name the sha to freeze at, and ask whether a push is genuinely needed before allowing one.

**Verdict the superset, never force a rewind.** When the last push before the freeze added only what you asked for (a missing pin, an exit code), that head is a strict superset of the one you froze and the right call is to verdict **it** — going back is a force-push, and a force-push is a push, so "restore the frozen sha" spends a matrix to arrive at a tree that is strictly worse. Confirm it only adds the requested work (`git diff <frozen> <new> --stat`, or check the files), then say plainly that the sha you verify is the sha that merges. The property that matters is *the verified tree is the merged tree*, not *the sha has a particular value*.

**Compare the tree before you decide what a moved head cost.** A re-push can be metadata-only or a real change, and the two have opposite consequences:

```bash
gh api repos/<o>/<r>/commits/<old> --jq .commit.tree.sha
gh api repos/<o>/<r>/commits/<new> --jq .commit.tree.sha      # identical ⇒ nothing was re-proven
```

Identical trees mean the cancelled run's successes still describe this code — the missing thing is a **conclusion**, not a result, and nobody should present the cancellation as "the code changed, the greens are void". Different trees void them, and a *commit rewrite* (an author fix, a rebase) changes the tree even when the diff is empty. Also check `parents`: a commit whose parent is the default branch rather than the previous head was rebuilt from scratch, not amended.

**When the same requirement is missing at successive heads, stop re-briefing in prose.** Rephrasing a demand a lane
has already ignored twice is the mistake; a measurement per head is not. Fetch the file from each ref and run it, then
post the table:

| head | empty diff | unknown path | pin in tests |
|---|---|---|---|
| `<sha>` | exit 2 | exit 1 | 0 |
| `<sha>` | exit 2 | exit 1 | 0 |

Then: **apply exactly this, prove it with these four one-liners, push once, freeze.** Paste the commands whose output
the lane must return (`jobs >/dev/null; echo $?` …), because a requirement stated as behaviour keeps being satisfied
"in spirit" while the exit code never changes. Four heads in one hour with the same two items open is a process finding
to name out loud — *"you have pushed four times and neither item moved"* — and then the rule: if either item is wrong
on the merits, argue in one message and the planner rules; do not push.

**Read the commit message of the next head, not only its diff.** A lane that disagrees with the ruling will encode the
opposite contract in prose — "no paths → exit 2, so the check is loud rather than quietly green" against a ruling that
says exit 0 — while the diff adds tests and docs. That is a disagreement, not an oversight, and it will not resolve by
re-briefing: state the ruling once more with the issue row that carries it, then take the branch off the lane rather
than negotiating through a sixth push.

**When the second proof table still shows no movement, take the branch off the lane.** That is what the table exists to trigger, and it is not a judgement of the lane's competence — a lane can add good tests for an hour and never touch the two lines the verdict waits on. Two messages, in this order:

1. **Stand the owner down explicitly**: no more pushes, no re-cut, no comments on that PR, and name what stays theirs so it does not read as a demotion.
2. **Hand the exact diff to a different implementer**: branch, PR number, current head sha, the lines with file and line reference, the proof commands, and *one push then stop*, in a worktree off that branch rather than the primary checkout.

Two lanes on one branch is the collision this avoids; one lane on it too long is the failure it fixes. Say which is which in both messages — the stand-down reads as blame unless it is framed as "the queue is not yours any more".
