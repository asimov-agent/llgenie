# engine-build-pr-trigger-head-sha

## Why

`.github/workflows/engine-build-pr-trigger.yml` keys its concurrency group by PR number alone
(`engine-build-pr-trigger-${{ github.event.pull_request.number }}`, `cancel-in-progress: false`).
The trigger awaits each dispatched producer run's own conclusion (issue #1633, #1102 never-cancel).
A `synchronize` push onto the same PR (a rebase — exactly what the rebase lane does to #1696) fires a
new trigger run that is queued by the per-PR concurrency group behind the already-running old-head
build for up to ~90 minutes (measured: run `42163068853`, head `321dabc826`, queued behind
`42155990380`). During that window the run reports `pending` / **0 jobs** / a frozen `updated_at`,
`gh run rerun` refuses it ("This workflow is already running"), and the rebased head has **no
producer at all**. A monitor that only reads status/jobs cannot tell a concurrency-queued run from a
genuinely-stuck scheduler.

## What changes

Scope the trigger's concurrency group key to the PR head SHA:

```yaml
concurrency:
  group: engine-build-pr-trigger-${{ github.event.pull_request.number }}-${{ github.event.pull_request.head.sha }}
  cancel-in-progress: false
```

`cancel-in-progress: false` is preserved, so a stale head never cancels a producer run that is
mid-build (#1102, producer's own guard and `engine-build-push` queue in `engine-build.yml` are
untouched, issue #917/#510/#1571). Because the key now includes the head SHA, a new push onto the PR
fires a NEW trigger run for the new head immediately (its `guard` job appears at once, and it
dispatches its own `push=true` producer run) instead of waiting behind the old head's build.

## Out of scope

The producer's own concurrency-queue behaviour and never-cancel semantics in `engine-build.yml` are
out of scope (issue #1831: "the producer's own concurrency-queue behavior ... are out of scope; this
issue is strictly the per-PR trigger group key"). No gate or severity is weakened.
