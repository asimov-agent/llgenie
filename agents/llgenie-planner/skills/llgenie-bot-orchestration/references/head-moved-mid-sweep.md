# A head that moves mid-flight voids the in-flight evidence run

Applies whenever a lane's acceptance criterion is *"run X completes success with the run id recorded here"*
(e.g. an engine-build sweep) and another lane rebases/refreshes the same PR.

## Rules

- **The evidence run must be at the head the PR will merge from.** A run started at head `A` stops counting the
  moment a rebase moves the PR to head `B`; filling its run id into the acceptance item produces a claim that
  cannot hold, and `make check-pr-acceptance` keeps failing on that item at the new head.
- **Never cancel the stale-head run to "free" the slot.** A cancelled run is not a verdict and teaches nothing;
  let it conclude, then re-dispatch at the current head.
- **Check for an existing run before declaring a lane idle.** Verify with
  `gh run list --workflow <wf>.yml --json headSha,...` filtered on the head sha, and
  `gh api repos/<owner>/<repo>/commits/<sha>/check-runs`. Absence of a *check-run* is not absence of a *workflow
  run*; an in-flight workflow run can predate your check by minutes.
- **A DM that "never answered within the wait" is not proof the lane did nothing.** `bot_mode_dm` returning
  `claimed` with "turn is still running, its answer will NOT wake you" means the request is on their side and
  unresolved — measure the wire (branch tip, workflow run, PR comment) before re-dispatching or recording idleness.
- **Steer on-issue, not by DM.** When the head has moved, comment on the linked issue with: old head, new head,
  the stale run id, and the exact ask — *let it conclude, re-dispatch at the new head, fill the run id (a fill,
  not a verdict tick), report head + run id here*. A DM is not durable and will not wake the planner.
- **Attribute the race correctly.** The rebase lane did the right thing (keeping the PR on latest main); the
  implementer's run simply became stale. Do not blame either lane — state the two head shas and the remedy.

## Fast check

```bash
gh api repos/$R/pulls/$N --jq '.head.sha'                       # current head
gh run list --repo $R --workflow engine-build.yml --limit 10 \
  --json databaseId,headSha,status,conclusion --jq '.[]|select(.headSha=="'$HEAD'")'
gh api repos/$R/commits/$HEAD/check-runs \
  --jq '[.check_runs[]|select(.name=="guard" and .conclusion=="failure")|.id]'
# then read the job log for the check-pr-acceptance violation line
```

**SKILL.md is over the 100 KB schema limit (103,315 chars at last check) — patches to it are rejected; add new
lessons as reference files here until the body is split.**
