# Failure-tracker acceptance names a cause class and a negative control (#2220)

## Why

`run-failure-reactor`'s `issue_body()` laid down the SAME three generic acceptance boxes for every
failed job, so a PR that simply re-ran the failing job could tick all three whether or not the
failure class recurs. Measured 2026-11-08: six open reactor trackers (#2156 #2157 #2164 #2185 #2184
#2160) were DIFFERENT symptoms sharing ONE cause class (a busy head's check-runs listing was read
one page of 100 and refused as "truncated", so the ci-verdict run died before writing a payload).
#2156 was fixed by a genuine class fix (#2161), and the class recurs because the acceptance cannot
tell a cause-class fix from a symptom patch.

When the acceptance names only a job and a rerun, a reviewer cannot refuse a symptom patch: the
three green boxes are satisfied by the same re-run that produced them, the class recurs, and the
reactor files a second tracker per re-judge.

## What changes

`scripts/run_failure_reactor.py` — the generic (non-pins-publish) `acceptance` list in
`issue_body()` now names:

1. the **failure class** the tracker names — `workflow/failing-step` from the failing step's logged
   error in the Technical tail, not the job name;
2. the **recurrence prevented** — a negative-control test that FAILS on the pre-fix tree and PASSES
   on the fix, proving the guard holds this class;
3. a **negative control** — the failing job's `databaseId`, which the guard must fire on.

The green-locally / green-on-the-same-job / `closes #<n>` boxes stay but are demoted to supporting
evidence. The pins-publish branch keeps its three publish-specific boxes unchanged.

## Who

ci-pipelines-maintainer (this lane owns the reactor's pipeline files).
