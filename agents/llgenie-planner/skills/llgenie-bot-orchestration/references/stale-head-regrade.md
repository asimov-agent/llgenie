# A lane grading an ANCESTOR head (stale-head re-grade)

A reviewer/judge lane quotes a head sha, a run id and a numbered defect list — and all three belong to an
**earlier commit on the same branch**, not the current tip. The run typically shows `event: pull_request`
from before the branch moved. Related but distinct from the merged-PR ghost loop
(`references/merged-pr-stale-rebase-loop.md`): that is a lane re-reporting a *merged* artifact; this is a
lane grading a *superseded but still-open* head.

## Detect it

```bash
gh api repos/<o>/<r>/pulls/<N> --jq '.head.sha'                                   # the LIVE tip
gh api repos/<o>/<r>/actions/runs/<RUN> --jq '{h:.head_sha,ev:.event,created:.created_at,c:.conclusion}'  # what the run graded
```

If the run's `head_sha` is an **ancestor** of the live tip (`gh api repos/<o>/<r>/compare/<live>...<accused>`,
or a plain `git merge-base --is-ancestor` on a deep clone), the verdict describes a superseded tree.

## What to do — neither relay it nor dismiss it

1. **Do not relay the ancestor's defect list as current.** Its failures may be entirely fixed by later commits
   (the tip often adds a cron-fix, a guard fix, or an author-gate fix on top).
2. **Do not ignore it either.** Re-measure the LIVE head yourself. The live head very often carries its **own,
   different** red — e.g. the ancestor's five conv-gate failures were fixed, but the newer commit added a test
   module that trips a different ratchet. The lane's "re-review owed at the next head" instinct is right even
   when its specific list is stale.
3. **Diagnose the live head's ACTUAL failing step** (read the failing make target / step log — see
   `references/actions-job-log-reading-midrun.md`), and dispatch that defect to the lane whose diff owns it, on
   the same branch (one-vehicle rule).
4. **Say on-record which head each fact is about** — name the stale head the lane quoted and the live head you
   re-measured, so the next reader is not left reconciling two "NOT GREEN" verdicts about different commits.

## Why it costs time

Repeating a stale-head verdict either re-dispatches already-fixed work or hides a genuine live red behind a
phantom one; dismissing it outright misses the live red the lane's instinct pointed at. Both failures cost a
full CI cycle. Always reconcile head-to-head before acting on any "NOT GREEN" claim.
