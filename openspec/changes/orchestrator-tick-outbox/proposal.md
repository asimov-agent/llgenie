# orchestrator-tick-outbox — proposal

Issue: [#1125](https://github.com/asimov-agent/llgenie/issues/1125)

## Why

The orchestrator tick keeps dispatching work that merged hours earlier, and every receiving lane
spends a turn disproving it. Measured tonight, by the lanes that received the dispatches:

```
#919          "rebase it, head e21e7b22"          CLOSED, merged 20:51:19Z (d3d9dd28) — 2.5h earlier
#1049/#1050   named as work to take              merged 20:03:39Z / 19:31:39Z
#885          "add the blank line at SOUL.md:39"  merged 21:50:58Z; lint on main says LINT OK
main 66d45b99 named as "the current main"        already superseded by ddcd2323
```

The cost is not the message. A stale dispatch is **indistinguishable from a fresh one**, so the
receiver must re-measure to tell them apart — and that produced three "your dispatch is stale"
replies, one mis-diagnosis (#1115 attributed to the wrong generator), and one wrong accusation from
the planner toward the rebase lane for arming PRs the tick had armed.

The mechanism is the one the rebase lane fixed in its own delta reporter: **the producer advances its
durable state before the side effect that consumes its output.** When delivery fails — and
`queue_full` is measured on this job — the in-memory delta is gone. The next pass diffs against the
already-advanced state, finds nothing new, and re-emits a task list from memory that still looks
current. A lost delivery is not late, it is unrecoverable.

Nothing in the repository encoded the properties that make a lost delivery recoverable, so no test
could fail when a producer lost one. That is what this change adds.

## What Changes

- **`scripts/orchestrator_tick.py` — the tick's dispatch producer**, mirroring the shape the rebase
  lane proved in its `tally-delta.py` reporter (append-only outbox + `[measured HH:MM:SSZ]` + delta
  keyed on the fact set), with the ordering corrected:
  1. the **append-only outbox** (`outbox.log`, one JSON record per fact) is written and `fsync`ed
     **before** the durable state advances, so a lost delivery is retried from the file;
  2. every emitted line carries the **measurement time of the fact it reports**, persisted in the
     record — a re-emitted line is visibly old instead of looking fresh;
  3. at **emit time** the subject's live state is asked (`gh pr view <n> --json state,mergedAt` /
     `gh issue view <n> --json state`); a subject whose PR merged or whose issue closed is dropped
     and recorded as suppressed, so it is never emitted again;
  4. the delta key is the **fact set** (`REBASE-NEEDED #919 @e21e7b22 mergeStateStatus=DIRTY`), never
     the run time — a second pass over unchanged state emits nothing and leaves the outbox
     byte-identical.
- **A delivery that fails to print does not acknowledge**: the lines stay pending, and the next pass
  re-emits the same bytes. An explicit `--no-ack` is the same shape (stdout thrown away), which is
  what the lost-delivery test drives.
- **A failed `gh` read fails loud** (exit 2) and leaves both the outbox and the state untouched — a
  read that failed must never look like "no change", the defect that started this.
- **`make orchestrator-tick` / `orchestrator-tick-pending` / `orchestrator-tick-report`** wire the
  producer, the recovery read and its numbers; `docs/BOTS.md` documents them beside the other
  hand-dispatch paths.

The tick's facts are only two, because those are the two the measured instances came from: a PR that
is `DIRTY`/`CONFLICTING` (dispatch the rebase bot) and an `agent:implement` issue with no live claim
(dispatch an implementer). A third kind is a new branch in `measure()` and nothing else.

## Benefit

- A `queue_full` on the tick's report is now a **retry**, not a loss: `make orchestrator-tick-pending`
  prints exactly what the delivery would have said, with the time each fact was measured.
- A dispatch that arrives late is **self-evidently late** — its `[measured …]` stamp is the one from
  the measurement, so the receiving lane can see the age without re-measuring GitHub.
- Already-merged work **cannot be emitted**: the check is the subject's live state at emit time, not
  a remembered queue, which is what the four measured dispatches needed.

## Not covered

- The tick's own prompt (the planner's cron job) is not edited here: the planner lane owns that
  profile and its live skill directory is not in the tree. This change ships the producer and its
  gates; wiring the cron leg to call `make orchestrator-tick` is the planner lane's sync, exactly as
  issue #791 requires.
- Richer fact detection (expired claims, branches with no PR) is a follow-up branch in `measure()`,
  not part of this mechanism change. Filed as its own issue when it is picked up.
