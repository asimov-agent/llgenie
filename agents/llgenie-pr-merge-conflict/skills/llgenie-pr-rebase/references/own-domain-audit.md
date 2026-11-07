# Own-domain audit contract (bounded, #1245 → #1852)

An empty reactive queue is one bounded own-domain audit, never an idle pass. When this lane's queue is empty
for N=2 consecutive passes, run ONE audit of **rebase-process gaps** and either file each finding as a refined
six-section issue tagged `agent:implement` through the normal implementer queue (never fix in the audit pass)
or record `re-audited at <sha>, no findings`. This lane does not implement beyond its own skill/behaviour and
its rebase remit.

## Re-run the audit against live API truth, never the last record (#1852)
The audit's entire value is that it measures at **read time**. For every head/base the lane has recorded in the
interval, re-read it from the API (`gh pr view <n> --json headRefOid,baseRefName`) and re-check ancestor-or-not
against the **current** `origin/main`, at the sha measured in that same moment. Points that must be re-measured,
never copied from a prior record:

- Each claimed PR head: is it still the live wire head, or did a sweep land after the record was written?
  The #1852 defect class — a lane cites `4c3ac6f7`/`bb0eb516` as "live" ~20 min after its own sweep landed
  `c139ca97`/`888e879a` — is a head that is *not re-measured at the moment of the claim, and the stale record
  is then repeated as if it were current.
- Every base used in the last N rebases must be an **ancestor of the current `origin/main`**:
  `git merge-base --is-ancestor <base> origin/main` — a base that is not an ancestor is a stale-base defect
  (the #1816 near-miss: main advanced via #1847 while the lane worked from a pre-advance target).
- Record for each item the sha you measured, so the audit record is itself checkable later.

## A finding's own witness must be read from `check-runs`, not reused
When the audit cites "vehicle X passed" as the contrast that proves a mechanical gate, read that PR's live
`check-runs` conclusions at its head before citing it. The #1850 defect class: the audit's dispatch cited
#1850 as "passed" on a stale witness while its live `guard`/`scope` runs at the head were red
(`check-pr-sync-line`, `check-pr-acceptance`). `MERGEABLE` is not a green gate; `cancelled` is not a pass.
A finding filed on a green you never measured is the same stale-read defect the audit exists to count.

## Defect scale and routing
One refined six-section issue per defect class found, filed through the normal implementer queue
(tagged `agent:implement`) — the audit lane files, never fixes in-pass. A clean audit is `re-audited at <sha>,
no findings` on the issue. One pass, no infinite loop, never overrides reactive work.
