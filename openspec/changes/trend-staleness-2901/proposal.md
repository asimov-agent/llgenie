# trend-staleness-2901 — proposal

Issue: [#2901](https://github.com/asimov-agent/llgenie/issues/2901) (staleness alarm for trend matrix drift), context #2900 / PR #2906

## Why

`tests/fixtures/trend-list-matrix.json` is re-pinned only when a render runs (`make
render-trend-list-matrix`, driven by the weekly registry-sync). Between renders the live trending
moves and nothing says so: the hermetic `--check` (issue #1080) replays the recorded snapshot, so a
fixture that matches its own recording is green even when upstream HF builds shifted under it. That
is exactly how main burned six consecutive `ci-hf-live` runs (#2900: the fixture pinned LFM2.5-24B-A2B
at 13 GB while the live trending build reported 9 GB) before anyone read the drift.

## What Changes

- **A staleness read in `scripts/trend_list_matrix.py` (`--staleness`)**: rebuilds the matrix against
  the live Hub (no writes) and compares it CELL BY CELL against the committed fixture, printing every
  disagreeing cell (`arch/vram/ram` + the rows that added/dropped/changed) and exiting non-zero when
  any cell disagrees; an unreadable stream (fixture or live build) exits 2, never a silent zero.
- **A make target `check-trend-list-fresh`** wrapping that read, so the gate is runnable locally and
  from the monitor lane (AGENTS.md: every CI-run command is a make target).
- **A new issue producer `scripts/trend_staleness_issue.py`** (registered in `issue_body.PRODUCERS`,
  body rendered ONLY through `issue_body.render`, deduped by a first-line marker): when the read
  disagrees it files ONE open refresh issue naming the disagreeing cells and ordering the re-render.
- **The ci-hf-live monitor lane surfaces the read** (the allow-listed twice-hourly monitor lane of
  #2701 — no new schedule lane): a step runs `check-trend-list-fresh`, and a disagreement files the
  refresh issue through the producer; a drift therefore becomes a tracked, ticketed work item instead
  of a recurring red battery, while an unreadable stream reddens the step.

## Not covered

- Nothing else — the detect-later gap is this issue's whole scope. The post-merge verification duty and the first re-pin already landed under #2900 / PR #2906; the landing watch is #2907.
