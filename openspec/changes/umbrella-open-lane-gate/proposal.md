# Proposal — hold a squash umbrella close while a referenced rollout lane is still OPEN (#1859)

The #1815/#1816 squash-text acceptance gate holds a close when the linked umbrella's OWN
`## Acceptance criteria` are unticked. It never reads a second issue, so a close that fires on an
umbrella whose own boxes are all ticked — but whose rollout LANE issues are still open — passes
GREEN (measured on this tree: `acceptance_verdict` on a 3/3-ticked umbrella naming open lanes
returns `[]`). #1849's recurrence (#1856's squash auto-closed it at 1/5 lanes) is precisely the
class this second half exists to stop, and #1816's unticked-criteria hold cannot see it once the
boxes are ticked.

The gate cannot hardcode lane numbers (issue #301: never a hand-kept roster). It must DERIVE the
lanes. Measured on #1849's own fleet, the signal is bidirectional citation: every lane vehicle
carries `#1849` in its own body, and every incidental reference in the umbrella body
(#1791/#1792/#1724/#791) does NOT carry `#1849` back. So a referenced-open issue whose body
names the umbrella is deterministically a rollout lane; a referenced-open issue that does not is
process context and must not hold the close. This change adds that check to the acceptance gate.

## Not covered

- Re-opening #1849 (satisfied by the recorded fleet-completion decision on #1849, comment
  `6684648298`: all five pointers verified on the merged head).
- The unticked-`- [ ]`-criteria hold itself (already shipped in #1816/#1815, fixture in main).
- Any change to `check_pr_closing.py`'s close-keyword parse.
