# llgenie-pr-merge-conflict-own-domain-audit

## Why

The lane's empty-queue own-domain audit (owner 2026-11-01, #1245) had no codified contract for *how* to
measure: a stale head/base claim cited without re-measuring it at the moment of use is the exact defect class
the audit exists to count (this pass: the lane cited `4c3ac6f7`/`bb0eb516` as the "live" #1837 head ~20 min
after its own sweep landed `c139ca97`/`888e879a`; the #1816 rebase nearly targeted the pre-advance
`24b97d50` base because main had moved via #1847). An audit that reads its own last record instead of the
live API truth has no value over idling.

## How

Codify the bounded own-domain audit contract as the lane's durable reference (`references/own-domain-audit.md`,
pointed to from the SKILL's empty-queue-audit section): every head/base the lane records is re-measured from
the API (`gh pr view <n> --json headRefOid,baseRefName`) at the moment of the claim, every base used in the
last N rebases is checked as an ancestor of the *current* `origin/main` (`git merge-base --is-ancestor`), a
finding's own witness is read from the changed PR's live `check-runs` conclusions (never a relayed
"passed"), and findings file as refined `agent:implement` issues (audit never fixes in-pass).

## Benefits

- The next sweep starts from a lane that measures at read-time, so the planner and owner stop being the ones
  who discover the lane's stale reads.
- A stale claim becomes a measurable defect with a tracked scale, not a silently repeated record.
- Green/red claims in audit records carry the sha they were measured at, so the record is itself checkable.

## Tasks

- [ ] Add `references/own-domain-audit.md` codifying re-measure-at-read-time, ancestor-or-not vs current
      `origin/main`, witness-from-`check-runs`, and defect scale/routing.
- [ ] Point the SKILL's empty-queue audit section at the new reference and name the two #1852 defect classes
      the lane now guards against.
- [ ] Change-note trio (agent-wiki + changes.d + CHANGES.md); check-docs / lint / sync gate green.
- [ ] Opened as READY-for-review PR (not draft), no merge/arm (#1088).
