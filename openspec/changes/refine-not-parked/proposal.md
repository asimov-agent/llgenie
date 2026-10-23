# A refine keeps the issue queueable

## Why

`scripts/issue_implementer.py` carried `DECIDED_LABELS = ("agent:refined", "agent:closed")`, and both
pickers (`_pick`, `_pick_free`) skip any issue carrying one. The refine verdict posts ONE comment with an
implementable restatement and labels the issue `agent:refined` — so the verdict that improves an issue also
removes it from the only queue that implements anything.

Measured on `main` (`1d36673`), issue #399: `state: OPEN`, `labels: agent:implement, agent:refined`, with a
refined restatement as its newest comment — and the picker skipped it forever. Measured on `main`
(`333344c`): 15 open `agent:implement`, 1 `agent:ready`, **3 open `agent:refined`** — those three are parked,
not queued.

The hourly `issue-refiner.yml` refines issues that are not yet implemented, so it stamps `agent:refined` on
unmodified backlog issues: the more often it runs, the less the implementer can reach. A refine was a
one-way door that needed a human label edit to reopen.

## What Changes

- **`agent:refined` is a marker, not a decision.** `DECIDED_LABELS` is now `("agent:closed",)`, so a refined
  issue stays in the picker with its improved specification. Module docstrings and the `--json` field list
  wording follow.
- **The refine verdict queues the restatement.** After the comment it adds `agent:refined`, and adds
  `agent:ready` when the issue carries no queue label — the issue is explicitly in the queue afterwards.
- **A second refine is refused**, not repeated: an issue that already carries `agent:refined` raises
  `SystemExit` instead of posting the same comment again (loop protection by a different signal, per #522).
- **Nothing else moves**: the refiner's own `SKIP_LABELS` still excludes `agent:implement` / `agent:ready`
  (it never touches a claimed issue), and `agent:closed` still ends an issue's life in the picker.

## Impact

- The refiner becomes a net improvement again: refined issues are implemented, not parked.
- The duplicate/canonical queueing (#521) now also queues a canonical issue that was refined but never
  queued — real open work with a better specification.
