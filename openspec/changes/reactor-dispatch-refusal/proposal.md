# Fix: a refused fix dispatch is posted on the PR, not swallowed by a red job

## Why

`run-failure-reactor`'s Route A shells `gh workflow run fix-bot.yml` as `DISPATCH_TOKEN`
(`secrets.BUMP_TOKEN`, `.github/workflows/run-failure-reactor.yml:94`) and the API refuses it:

```
dispatch failed: could not create workflow dispatch event: HTTP 403: Resource not accessible by
personal access token (…/actions/workflows/384587805/dispatches)
```

Measured run `42442836444`, job `react` `128615515251`, head `e51f2fd0`, 2026-11-08T03:28:16Z
(#2086). Two things make that refusal invisible:

1. Only a red PR reaches the dispatch — a green reactor prints `conclusion is 'success' - not a
   failure, nothing to do` — so no green run ever exercises the leg;
2. the old code raised a plain `RuntimeError`, so `make run-failure-reactor` exited 1 and the whole
   `react` job went red on `main`'s tip, which reads like a main-tip failure while the PR it was
   trying to repair said nothing at all.

The claim written just before the dispatch also stayed behind, keeping every other bot off that PR
for the whole claim TTL although no repair had started.

## What changes

A non-zero `gh workflow run` becomes a `DispatchRefused` that carries the HTTP **status** and the
**scope the credential lacks**. Route A catches it, posts `repair unavailable: HTTP 403 — missing
scope: …` on the PR together with the claim's own `bot-done` release, emits a `::warning::`
annotation, and returns 0 — the reactor's own reds keep meaning "the reactor broke", while the branch
that needed a repair reads *no repair*. An unrecognised refusal is surfaced the same way (`HTTP ?`),
never swallowed.

The credential itself (`workflow` on a classic PAT, `Actions: write` on a fine-grained one) stays the
owner's decision — #2091, which also records that `docs/BOTS.md:2633` already prescribes
`${{ github.token }}` and that `fix-bot`'s guard now admits `github-actions[bot]` on a
`workflow_dispatch` (#1571), making the #555 premise stale.

## Who

ci-pipelines-maintainer (this lane owns the reactor's pipeline files).
