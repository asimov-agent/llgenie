# A gate PR reds on its own gate — unblock with a reviewer verdict, never a weakened gate

## Symptom
The PR that *introduces* a merge-time acceptance gate reds on that very gate. The gate reads the
LIVE linked issue at its own CI run time; the PR carries `closes #N`; issue #N's `## Acceptance
criteria` boxes are still `- [ ]` because the issue is open. The new `claim-unchecked` verdict
fires against its own author. The lane reports this honestly as "the gate working correctly, not a
bug" — believe it; do not treat the red as a defect to fix by editing the gate.

## Why it is real, not a false alarm
- The gate is verification-only and reads merge-time live state (fleet rule: post-merge measure,
  never the pre-fetch head).
- The tick seam (`acceptance_writeback`, issue #1644) ticks boxes **only** on a reviewer's
  COMMENTED verdict. An auto-merged / bot-authored PR never gets one, so the boxes never tick on
  their own — a genuine chicken-and-egg for the introducing PR.

## The sanctioned unblock (route the planner takes)
1. Dispatch the reviewer lane (`llgenie-pr-reviever`) to review the gate PR at its exact head sha
   against the issue's criteria, quoting a fresh **completed** run id as evidence (default-defer-
   not-fabricate: quote the run, never assume).
2. Reviewer posts an explicit COMMENTED verdict ("Accepted: all N criteria met at <sha>, run <id>").
3. `acceptance_writeback` (#1644) ticks the issue boxes on that verdict.
4. Next CI run: the `claim-unchecked` red clears because the boxes are now checked. Then arm
   auto-merge per the standing rules.

## Forbidden resolutions
- Weakening / bypassing the new gate, or editing it to exempt its own PR.
- Manually ticking the issue boxes (fakes the one proof the gate exists to demand).
- Opening a second vehicle for the same issue (one vehicle per issue).
- Owner direction to "just tick" is a last resort, offered only if the reviewer route cannot run —
  and even then it is the owner's word, not the planner's.

## The unblock requires the head to still be CURRENT — a concurrent merge voids it (order: rebase THEN review)

"Review the gate PR at its exact head sha" (§ The sanctioned unblock) is only correct while that
head is still the vehicle's live head. If ANY other PR merges after the head was cut, main advances
past the head's base, the head becomes base-stale (`check-pr-base` #845/#1015 class reds on the next
full run even though the self-red was cleared), and a reviewer verdict + `#1644` tick posted against
that head are wasted — a run at the superseded head is void. Re-read live main BEFORE dispatching
the reviewer:

```bash
git fetch origin main && git rev-parse origin/main        # live tip at this instant
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha[0:8],base:.base.sha[0:8]}'
git merge-base <head> origin/main                          # == origin/main? then head is current
```

If `merge-base(head, origin/main) != origin/main` (main moved after the cut), the order is **rebase
first, then review**: dispatch the OWNING lane to rebase onto the freshly-fetched tip (refresh the
body `AGENTS:`/`BASE:` citation to the same sha + its units), and HOLD the reviewer — tell it
plainly "do not post the verdict/`#1644` tick at <old-head>; stand by for the rebased head." Only
dispatch the reviewer once the rebased head's parent IS live main. Posting the verdict first means
the tick lands on a head that must rebase, and the next run re-reds on the base gate — one wasted
reviewer run and a re-dispatch. Recording the merge on the board (main advanced <old>→<new>, #N
merged, this PR now base-stale) is the durable trail; the reviewer re-review and the tick move to
the rebased head in the same order.

## A criterion that can only be proven POST-merge is a designed held-box — do not press the lane to clear it

Some criteria are unknowable before the merge ("the 360m cap is on main", "the new pin serves"). Ticking
them pre-merge is fabrication; leaving them `- [ ]` keeps `check-pr-acceptance` at one honest violation.
That one-red state is a **house terminal**, not a defect: before prescribing any remedy, measure the
precedent — an earlier introducing PR sitting at exactly this shape (`AC-N` unticked, issue OPEN,
introducing PR `mergeStateStatus: BLOCKED` — e.g. #1812 AC5 holding #1804) proves the repo accepts it.

- The `## Not covered` + linked-work-item escape (see `pr-closing-gate.md`) is **sanctioned but
  OPTIONAL**. Offering it is fine; presenting it as the required edit is over-prescription, and a lane
  that cites the precedent is right to refuse.
- Fully green is only reachable by faking the write-back. Never argue for it: the hold is the truth.
- Correct shape of the planner's report: `green-except-the-designed-hold`, the run id + exact violation
  count, the precedent PR/issue pair, and the release path (owner merge → criterion provable → its own
  write-back). Concede on-issue in one comment when a lane's precedent check beats your remedy — the
  concession is the durable record, not a DM.

## Planner's job here
Verify the wire (PR number, head==pushed, base==main, the issue boxes all unticked), echo the PR
number back if the lane's read channel is degraded and cannot render it, state the routing decision,
and dispatch the reviewer. The lane keeps the one vehicle and holds until the verdict lands.
