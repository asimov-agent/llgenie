# engine-build-pr-trigger head-SHA concurrency scoping (#1831)

**Issue:** #1831 — engine-build-pr-trigger: per-PR concurrency group serializes a rebased head's
dispatch behind the old head's build.

## What was verified against the spec

Spec: `openspec/changes/engine-build-pr-trigger-head-sha/specs/engine-build-pr-trigger-head-sha/spec.md`.

1. **Rebased head gets a real `guard` job immediately.** `.github/workflows/engine-build-pr-trigger.yml`
   concurrency group is now `engine-build-pr-trigger-${{ github.event.pull_request.number }}-${{ github.event.pull_request.head.sha }}`,
   so a `synchronize` push (e.g. the rebase lane on #1696) fires a NEW trigger run for the new head
   with its `guard` job present at once, instead of a `pending`/0-jobs/frozen-`updated_at`
   concurrency-queued signature behind the old head's build. The measured victim is documented in the
   issue: run `42163068853` (@ `321dabc826`) queued behind `42155990380`, invisible to a status/jobs-only
   monitor, `gh run rerun` refusing ("This workflow is already running").
2. **The new head dispatches its own producer run.** Because the key includes the head SHA, the new-head
   trigger no longer waits for the old-head producer to conclude (~90 min per rebase); it dispatches its
   own `push=true` engine-build run at its head SHA without any `gh run rerun`.
3. **Never-cancel preserved.** `cancel-in-progress: false` is unchanged; the producer's own guard and
   `engine-build-push` concurrency queue (`engine-build.yml`, #917) are untouched. No gate weakened.

## Decisions taken

- Scope only the trigger workflow's `concurrency` block; the producer workflow and all guards are out
  of scope per the issue's own "Out of scope" (strictly the per-PR trigger group key).
- The key concatenates PR number and head SHA (a change in what a per-PR static group serializes), so
  `cancel-in-progress: false` still means a stale head never cancels a live producer run (#1102).

**PR:** #1831 vehicle. **Gates:** `make check-workflows` + package-unit green at the head.
