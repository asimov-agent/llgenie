# 2026-11-26 — a named trend drift carries its cells to the filing path (issue #3057)

## What was verified against the issue

- The failure is the issue's own measured numbers (run `45366360390`, `hf-live`): `make
  check-trend-list-fresh` NAMED a 4-cell drift (`metal/24/8|24/32/24/60/24/64`, Gemma 3 27B `6 GB > 10 GB`
  -> `10 GB > 10 GB`, fingerprint `866ec6ad00f3`), exited 1 — and the step still concluded **exit 2** with
  zero `trend-staleness-issue` output: the producer re-ran the whole live trending read, the second read
  hit the Hub blip, and the earned ticket vanished (issue #2901's steady state broken silently).
- The fix is a handoff, not a retry: `staleness_read()` now records the cells it NAMED into
  `build/trend-staleness-drift.json` (transient, gitignored via `.gitignore:6`), a fresh read (exit 0)
  REMOVES that handoff so a retired drift can never be filed from it, and an unreadable read (exit 2)
  leaves it untouched — a blip never erases a ticket a completed read already earned.
- `trend_staleness_issue.py::named_drift()` consumes the handoff BEFORE any read: when it is present the
  filing path files from it with **no second live trending build** (test pins this by stubbing
  `staleness_read` to raise); a handoff it cannot trust is reported by name and falls back to the
  producer's own read. Standalone with no handoff, a failed re-read prints
  `[trend-staleness-issue] FAIL ... staleness re-read could not run ...` before the exit code.
- The `ci-hf-live.yml` step shape: the filing call is guarded (`make trend-staleness-issue || rc=$?`), a
  filing failure is named and re-raised as **3**, and the check's own unreadable read still lands as its
  loud 2 — the step can no longer pass exit 2 through the filing branch.
- The dedupe marker `<!-- trend-staleness: <fingerprint> -->` stays the body's first line and fingerprints
  the HANDED-OFF cells, so the producer's memory of what it filed survives the handoff.

## Key decisions

- One read owns the live trending; the filing path is a consumer of its verdict (#3057's core rule).
- Exit codes keep their distinct meanings: 1 named-drift-ticketed, 2 read-could-not-run, 3 filing-failed.
- Log lines use `trend_list_matrix.shown_path()` so a handoff outside the repo (tests) never crashes a print.

## Current status

- Bounded tests: `tests/test_trend_list_matrix.py` + `tests/test_trend_staleness_issue.py` +
  `tests/test_ci_hf_live_workflow.py` — 104 passed, 0 skipped (synthetic pairs only, no Hub reached).
- The 4-cell re-pin itself is NOT this lane's scope: side issue **#3056** (its re-render landed earlier
  this day); the live proof of this fix is the next `ci-hf-live` green that files from a named drift, read
  by `make -s post-merge-live-check`. OpenSpec change `trend-staleness-filing-3057`.
