# Design — liveness-dispatch-coalescing (#2579)

## Key decision: coalesce on the line count, keep both dispatch shapes

`engine-build.yml` already defines the sweep: `engine` empty = every engine, `arch` empty =
every variant, `push=true` publishes each cell from its own green job (measured: fleet run
#645 published 27 cells while one cell red-ed). So the coalesced shape needs no new producer
input — only the consumer stops firing N runs when it can fire one.

Threshold is the `[select]` line count: N>1 → one sweep dispatch (`-f push=true` only);
N==1 → today's per-cell dispatch (`-f engine -f arch -f push=true`). A per-cell wave matters
because every run lands in the single `engine-build-push` concurrency group and queues behind
whatever sweep is already running; one sweep dispatch occupies exactly one slot.

## Shape: validate first, then choose the dispatch path

The step first runs ONE `while read -r sel engine variant tag extra` loop over `select.txt`
that ONLY validates the contract (#2567 locks keep this loop as the single consumer of
select.txt, with the marker bound in its own field and `bad_line` failing the step after the
loop). Dispatch happens after validation: sweep when the count is >1, per-cell when it is 1.
A sweep therefore still requires contract-clean lines — a malformed gate report never becomes
an unattributed sweep either.

## Rejected

- Cancelling superseded queued dispatches (priority preemption): the issue lists it as not
  covered; cancelling in-flight producer work is what #2570's unattributed cancels proved
  dangerous.
- `dispatch_id`/queueing rest API tricks: the workflow's `gh workflow run` seam is already the
  sanctioned dispatch path (engine_build_trigger.py, #2089 one-field-per-input discipline).
