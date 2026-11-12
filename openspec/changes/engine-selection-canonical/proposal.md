# engine-selection-canonical — proposal

Issue: [#2516](https://github.com/asimov-agent/llgenie/issues/2516) (the registry-liveness
dispatch contract — engine ids parsed from package URLs fabricated a green no-op)

## Why

The registry-liveness self-remediation wave for merge `aa700cf27` (#2517) dispatched 28 scoped
`engine-build push=true` runs on main. 19 built their cell correctly; **nine completed `completed
success` having built and published nothing** — their build jobs are named
`engine-build-none-none` and every build/push step was skipped. The cause is measured:
`scripts/engine_image.py matrix()` matches the dispatched `engine` input against committed params
**id**s, but the dispatch step reconstructed that id out of a GHCR package URL. Package names
legally replace dots with dashes (`params['id'].replace('.', '-')`, `scripts/engine_image.py:1246`),
so `llama.cpp` arrived at the workflow as `llama-cpp`, `matrix()` matched no committed id, emitted
the `none` placeholder and exited 0, and `engine-build.yml` skipped every step of a `none` row.

## What Changes

- **`scripts/check_engine_pins_published.py`** emits one machine-readable `[select] <engine-id>
  <variant> <tag>` line per unpublished cell on the `--all` sweep, using the committed params id —
  dots intact. The registry is a namespace where dots are illegal; the params id is the canonical
  name.
- **`.github/workflows/registry-liveness.yml`** dispatch step consumes ONLY those `[select]` lines.
  It no longer parses engine ids out of package URLs, so a dotted id reaches `engine-build.yml`
  exactly as committed.
- **`scripts/engine_image.py matrix()`** exits non-zero naming the selection when an explicit
  `--engine` / `--arch` resolves to zero committed cells ("no committed engine id `llama-cpp`", or
  "`llama.cpp` has no committed variant `metal`"). The `none` placeholder remains ONLY for the
  unscoped sweep (`--changed` with nothing moved, whole-fleet sweeps), its documented intentional
  no-op. This also reddens `make engine-build-matrix ENGINE=<typo>` and
  `make build-engines ENGINE=<typo>`, today silent no-ops.
- **Tests** pin all three behaviours, including a replay of the incident: `--engine llama-cpp`
  (the package spelling) must fail, and the `[select]` lines for dotted cells must carry
  `llama.cpp`, never `llama-cpp`.

## Out of scope

- The full 28-cell fleet-publication proof after the queued dispatches drain is its own issue
  (#2529), which this dispatch-contract fix serves.
