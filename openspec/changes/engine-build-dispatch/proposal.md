# engine-build-dispatch — proposal

Issue: [#614](https://github.com/asimov-agent/llgenie/issues/614)

## Why

Engine images are built inside `ci.yml` (`engine-base` → `engine-matrix` → `engine-image` →
`engine-published-test`), and `engine-matrix` filters to the images a PR **changed**
(`CHANGED=<base>`). That is the right merge gate, but it means no run ever exercises the whole
pinned set: a stale-but-unbuildable pin, or an image that drifted from its params, is only found
when that engine is next touched. There is also no dispatchable form for the sweep — a maintainer
who wants to validate the current pins has to fake a change that touches every engine.

## What Changes

- **`.github/workflows/engine-build.yml`** (new, `workflow_dispatch` only): guard job first, then a
  matrix job that calls `make engine-build-matrix ENGINE=… ARCH=…`, then one `build` job per row
  (`max-parallel: 20`) running `make build-engine` followed by `make test-engine-stage` in the row's
  own mode (`serve` for cpu, `detect` for GPU). Inputs: `engine`, `arch`, `push` (publish, default
  false). No `pull_request`, `push` or `schedule` trigger.
- **`make engine-build-matrix`** (new target): `scripts/engine_image.py matrix --json --ci` with
  `--engine` / `--arch` filters added to `matrix()` and the CLI, so the sweep's rows are the
  committed params and never a hand-written roster.
- `ci.yml` is unchanged: it keeps the changed-images gate. Removing it would let an unbuildable
  engine bump merge (see the issue's *Not covered*).
- README documents the workflow, the target, and the source-vs-prebuilt split (13 of 31 variants are
  prebuilt today; converting them is issue #615).
- `tests/test_engine_build_workflow.py` locks the workflow's shape: dispatch-only, guard first,
  matrix from the committed params, every row built **and** verified, publishing off by default.

## Benefit

A maintainer can verify every engine at every pinned version in one dispatched run, and a broken pin
is found before the next bump touches it. The sweep costs nothing on ordinary PRs, and the workflow
builds whatever the params say — so a variant converted to a source build (issue #615) needs no
workflow change.
