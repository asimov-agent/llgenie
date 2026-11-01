# Where a tracking record belongs

A record only counts where the work lives. A blocker, a routing decision, a remedy, or a
dispatch that exists only in a host DM or a kanban card does not exist for the next reader; mirror
it to the issue/PR thread and quote the comment id.

## One vehicle, N issues: record on EVERY covered issue

When a single PR/branch covers two or more issues (e.g. a joint security pair), posting the blocker
and its remedies on the primary issue only leaves the others GitHub-silent. A reader who arrives
from the secondary issue sees no owner gate, no remedy list, and no "work is preserved" note, and
re-dispatches a lane that will re-hit the same wall.

- Post the full record on the primary issue; post a trimmed mirror (same blocker, same remedies,
same state) on each sibling issue, cross-linking the comment ids.
- Then measure, do not glance. Count comments per covered issue:

```bash
O=asimov-agent; R=llgenie
for n in <id1> <id2>; do
  echo "$n: $(gh api repos/$O/$R/issues/$n/comments --jq 'length')"
done
```

Any `0` on a joint-vehicle issue is the gap — fix it before reporting the pass complete.

## Guard loops: answer with a measured gap, not another dispatch

When the completion/progress guard fires *after* you already made a verified board mutation, do not
escalate by stacking more dispatches (docs → ci-pipelines → architect → …) — that is fan-out
without fresh measurement, and three correct-looking dispatches are still manufactured work if no
new fact drove them.

Instead pick ONE concrete, measured unreconciled thing and fix it: an issue with zero comments, a
PR head you have not re-read since the last push, a fork ref vs canonical mirror divergence, an
unverified "done" claim. Fix it, read the id back, and state the loop-escape decision explicitly on
the tracking thread ("holding; dispatch chain ends here; a red check is preferred to manufactured
work"). A guard left unsatisfied is the correct outcome when the alternative is invented work or
editing a lane you were not dispatched for.
