# fix-engine-build-trigger-path-filter

## Why

The `engine-build-pr-trigger` "will" arm of the pin-bump gate (issue #1633) has **zero
successful runs ever** (measured at main `171b4fe7`, and again live today): 34 failures, 29
cancelled, 1 pending across the workflow's history — including PR #1982, whose `trigger` check
reds on every attempt with a near-empty failure `[will] FAIL engine=…: run  concluded
queued/None` (an EMPTY run id). Treating it as a "stale race that a re-run clears" is wrong: the
re-run (run `42396610033` attempt 2) dispatched a fresh producer (`42399388147`) and failed
identically.

Root cause, measured live against the GitHub REST API: `scripts/engine_build_trigger.py`
filters the run list with `.path == "/.github/workflows/engine-build.yml"` (a leading slash that
GitHub does not return). The API reports `.path == ".github/workflows/engine-build.yml"` (no
leading slash) — the leading-slash jq filter matches **0** runs, the no-slash filter matches
**21**. So `_existing_run_ids()` always returns ∅, the discovery loop in `_dispatch_and_wait`
never sees the producer it just dispatched, and DISPATCH_TIMEOUT (90 s) fires with `run_id=""`.
The whole "await the NEW run's own verdict" discipline is dead in production. Because the unit
test mock hardcodes the same wrong leading-slash string
(`tests/test_engine_build_trigger.py:53,68,74`) and `fake_gh_api` never applies the `.path`
filter, the suite passes while real dispatch always fails.

## What changes

Drop the leading slash from the two real GitHub run-list filters, so `.path`
matches the API's actual shape:

- `scripts/engine_build_trigger.py:95` (`_existing_run_ids`)
- `scripts/engine_build_trigger.py:180` (`_push_group_holder`)

and fix the unit-test mock to the true API shape (`".github/workflows/engine-build.yml"`) so a
regression in the filter spelling reds the suite instead of being encoded as "correct". No
change to what the gate checks, to `enforce_events`, or to the dispatch/dispatch-guard logic —
this only makes the existing "find the newly-dispatched run and await its verdict" discipline
actually work.

## Out of scope

- #1831 (per-PR concurrency), #1860/#1931 (stalled/cancelled producer) — distinct trigger
  classes, already tracked.
- Any change to `check-engine-pins-published` (the "may" arm) or to `engine-build.yml`.
