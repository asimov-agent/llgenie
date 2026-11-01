# Measurement-report deliverables and close verification

## A report comment is landed work, even with no branch and no PR

Some issues are measurement/analysis deliverables (`agent:implement` but the acceptance is
"measure and recommend"). The lane lands them as a **comment on the issue**: run-id-bound
tables, p50/p95 windows, dominant-step breakdowns, a recommendation. There is no branch and
no PR, so branch/PR scans show the issue as unclaimed.

Before forcing an idle lane onto a "lounging" issue, **read the issue's comment timeline**
for a report comment. Forcing past a landed report is the same error class as acting on a
stale premise: you re-dispatch work that already exists and the lane has to re-explain
itself. If two report comments exist on one issue, reconcile them before judging — a wider
window can be contaminated by a superseded ceiling or a single starvation outlier, so the
narrower post-change window is usually the honest steady state; say which one you are
adopting and why.

## "Deliverable complete + lane idle" does not mean the issue is closed

A lane that reports "measurement finalised, idle for next routing" may have left the issue
open and still labelled `agent:implement`. That is an open vehicle on an idle lane, not
idleness. Always check the API before accepting "idle":

```
gh api repos/<org>/<repo>/issues/<n> --jq '.state, .closed_at, [.labels[].name]'
```

`state=open closedAt=NOT-CLOSED` with `agent:implement` on a self-declared-idle lane = force
the explicit close (`gh issue close <n>` with a close note citing the evidence comment ids
and restating the finding), then require the lane to report the close confirmation. Never
accept the lane's self-description as the evidence; the API is the evidence.

## Verify, don't trust, the numbers you relay upward

When relaying a lane's measurement to the owner, re-read the comment ids it cites (they must
exist, be by the lane, and contain the claimed numbers) before repeating them. Quote the
comment id you verified against.
