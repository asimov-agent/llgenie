# Two lanes disputing one file: measure the bytes at both heads

When lane A says "the fix is already on branch X's head" and lane B (even the fix's author) says
"it is not" or "it trades another defect," neither reading is evidence. Diff the actual blob:

```bash
git fetch origin <branch>
diff <(git show <headA>:<path>) <(git show <headB>:<path>)
git show <headX>:<path> | grep -n '<symbol>'
```

Read the region; do not repeat either lane's reading.

## A present line is not a complete fix

Worked example (#1753): a lane claimed #1696's head was "byte-identical to main" — it was not (a
real 2-line builder diff). A second lane claimed the same head "carries the fix." Both partial-right:
the head had an **unconditional** `--builder default` that fixes the FROM-base red but RE-BREAKS the
`CACHE_WRITE` cache-export that main's `not CACHE_WRITE` guard was merged to fix. The complete fix
was a third thing (driver-conditional selection). Lesson: check what a change COSTS, not just that
the line is present — two defects can trade one for the other.

## Stop flip-flopping

If you have flipped the same routing on successive lane messages, pin it to the measured bytes and
say so on the durable thread. A correction post names the comment id it supersedes (e.g. "corrects my
6650386759") so the next reader sees the trail rather than two contradictory instructions.
