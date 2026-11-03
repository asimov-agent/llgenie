# 2026-11-03 — a pin-bump PR triggers the engine-build producer (issue #1633)

The #1622/#1631 "may" arm (`make check-engine-pins-published`) stopped a pin-bump PR merging before its
image was published, but nothing on the PR side started the producer. Issue #1633 is the "will" arm that
closes that gap.

- New `scripts/engine_build_trigger.py` finds the engines this change repins via
  `check_engine_pins_published.repinned_engine_ids` (the params-FILE diff — one shared repin logic, not a
  roster) and, for each, dispatches `engine-build` with `push=true`, then awaits THAT run's own verdict
  (`gh workflow run` exit 0 is never a verdict — the #964 discipline, same diff-before/after as
  `scripts/all_pipelines.py`). A run refused at the producer's own trigger guard is reported
  `NOT VERIFIED — refused at its own trigger guard`, never a bare failure.
- New `.github/workflows/engine-build-pr-trigger.yml` fires on `pull_request` narrowed to
  `containers/engines/params/**`, gates on a same-repo head (a fork bump never reaches a push=true
  dispatch — issues #510/#1571), sets `cancel-in-progress: false` so a stale-head PR never cancels a live
  producer run, and calls `make engine-build-pr-trigger`.
- `engine-build.yml` is UNTOUCHED: its owner/collaborator-with-write guard still runs before any secret,
  and a push=true dispatch joins the producer's own `engine-build-push` concurrency group (issue #917).
- No repin => hermetic green, zero dispatch — the same "no engine repinned => green and no network" rule
  as the may arm (issue #1622).

Implements issue #1633.
