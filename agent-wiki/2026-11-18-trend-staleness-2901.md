# Trend-matrix staleness alarm between re-renders (issue #2901)

## What was verified

Issue #2901: `tests/fixtures/trend-list-matrix.json` was re-pinned only by the weekly
registry-sync render, while upstream trending edits continuously — the LFM2.5-24B-A2B
smallest-GGUF size moved 13 GB → 9 GB between renders and five consecutive `ci-hf-live`
runs (ending at run 44212692903) were the FIRST signal of that drift.

Measured on 2026-11-18 with this lane's read against the live trending (commit under test):

- `make -s check-trend-list-fresh` named **4 disagreeing cells** (`metal/16/8`,
  `metal/16/32`, `metal/16/60`, `metal/16/64`, each `LFM2.5 24B A2B` / `LFM2.5-24B-A2B`
  showing `13 GB -> 9 GB`) and exited 1.
- `make trend-staleness-issue DRY=1` rendered the refresh issue body for those cells —
  six sections via `issue_body.render`, dedupe marker `<!-- trend-staleness: <fp> -->`
  first line — and exited 0; the dedupe search read GitHub back (#2901 itself was
  correctly NOT counted as "already filed" because it lacks the marker).

## The fix

1. **`scripts/trend_list_matrix.py --staleness`** (`staleness_cells` + `staleness_read`) —
   builds the matrix against the LIVE Hub with no writes and diffs it cell by cell
   (added / dropped / changed rows + the engine-variant fingerprint as its own named
   cell). A disagreement exits 1 naming every cell; an unreadable fixture or a failed
   live build exits 2 — a read that could not run never reports fresh.
2. **`scripts/trend_staleness_issue.py`** (producer registered in
   `issue_body.PRODUCERS`) — files ONE open `agent:ready` refresh issue naming the
   cells and ordering `make render-trend-list-matrix`. Dedupe: a hashed drift
   fingerprint inside the body-first marker, and an open-marker search before filing;
   a failed dedupe read refuses to file (exit 3), a failed delivery exits 3.
3. **Wiring without a new clock** (the #2701 schedule allow-list holds): the existing
   `ci-hf-live` monitor lane runs `check-trend-list-fresh` before the network battery;
   drift files the ticket and the step stays green (the hermetic contract check remains
   `check-trend-list-matrix`; the battery still fails loudly on its own). An unreadable
   read (exit 2) reddens the step. The job gained `issues: write`.

## Verified against the spec

`openspec validate trend-staleness-2901` passes; the spec's two scenarios are the two
new hermetic tests (`tests/test_trend_list_matrix.py`: named-drift cells + fingerprint
delta + both exit-2 paths; and the producer's body-shape/marker test). `make
check-package-layers` is green with the two new stated edges
(`trend_staleness_issue → trend_list_matrix`, `→ proc`).

## Current status

Detection + filing ship with this lane. The live drift named today (13 GB → 9 GB) is
the same drift #2900's re-pin (PR #2906) re-renders; whichever lands first, the next
`ci-hf-live` run either confirms green (re-pin merged) or files the dated refresh issue
(marker-deduped) — the gap of "first alarm = red battery" is closed either way.
