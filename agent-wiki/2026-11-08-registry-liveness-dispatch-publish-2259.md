# registry-liveness now dispatches the publish it names (issue #2259, PR #2261)

A committed engine tag that 404s on GHCR is a **partial publish the pipeline produced and nothing
repaired** — not an accident. `registry-liveness` already NAMED the gap (issue #1682/#1684, open five
days) but never performed the publish, so a committed-but-unpublished pin sat red until a human ran
`engine-build` by hand. Issue #2259 closes all three absent halves.

## What changed

**1 — the gate now dispatches the publish (`.github/workflows/registry-liveness.yml`).** After the
`ALL=1` hard-fail (kept **verbatim** — no gate weakening), a new `always()` step parses each
`NOT PUBLISHED <pin8>-<hash8>-<variant>` tag out of the fleet-gate output, derives `engine`+`arch`,
and runs `engine-build` with `--field push=true` for every missing cell. It grants `actions: write`
on **this** (the caller) workflow — the minimum the `gh workflow run` producer needs — while
`engine-build.yml`'s own `packages: write` and the fork guard stay untouched.

**2 — the sweep no longer silently strands later cells (`scripts/engine_image.py`).** New `collect`
command: attempt **every** enabled CI cell of an engine as ONE sweep — success is built (and pushed
when `--push`), a failure is NAMED on stderr, it does not stop the next cell, and the exit is 0 only
when every cell succeeded. A repin is all-green or explicitly partial, never silent.

**3 — the filed issue names the real remedy (`scripts/run_failure_reactor.py`).** For the
registry-liveness / pins-publish failure class, the "no PR this bot can repair" body is replaced with
a publish-specific one: confirm the dispatch, land `push=true`, keep the issue open until the tag
resolves a manifest.

## Verification

- Workflow-shape test: the dispatch step fires `engine-build push=true` for a `NOT PUBLISHED` vllm
  cuda/rocm tag; the `ALL=1` hard-fail assertions are unchanged.
- Sweep-collect regression: cpu fails, cuda/rocm still attempted + named, successes published.
- Repin lock: an install-line change at an unchanged `pinned` still repins the engine (the #2259 red
  herring).

This is the behavioural change-note for #2261 (closing #2259); the product code landed in that PR.
