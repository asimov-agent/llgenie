# Refreshing docs/ARCHITECTURE.md for the tree at 20261112T0750 (issue #2565)

## What changed

`docs/ARCHITECTURE.md` lagged the tree — last updated at `49f0cc3be983`, with 3 commits and
68 changed paths since — so the architecture bot re-derived the surface and the drift from
real `git` state at `c4734a02` and rewrote only the doc. PR #2566 carries that one file on
`agent/architecture-20261112T0750` (measured at `87057b65d`).

Notable deltas the re-derivation wrote in:

- The non-root served-image contract (issue #2504): every shipped engine image serves as
  uid/gid 1000 via the generator-side `USER 1000:1000` in `scripts/engine_skills.py`
  (`render_base_dockerfile` / `render_dockerfile`), idempotent against upstream bases that
  already own 1000, with `USER root` re-enabled after each `FROM` for build stages; the
  negative control is measured — trivy `DS-0002` findings went 37 on `origin/main` to 0 at
  the #2504 head. `containers/test/Dockerfile` is deliberately OUT of the sweep and is
  deferred to the #2518 publish-order lane.
- The engine-selection `[select]` contract (issue #2561): an explicit `--engine`/`--arch`
  request resolving to no committed cell is a name error — `matrix()` raises `SystemExit`
  naming the id and the committed variants — instead of the old `engine-build-none-none`
  green no-op (the nine green runs at `aa700cf27` came from a ghcr package name, dots
  replaced, matching no params id).

## Current status

The bot commit touched only `docs/ARCHITECTURE.md` (as `Asimov Agent <support@docondee.com>`);
this change-note trio (`agent-wiki/2026-11-12-architecture-refresh-2565.md`,
`docs/changes.d/2026-11-12-architecture-refresh-2565.md`, and its `CHANGES.md` index row) is
the docs obligation the refresh owed (`make check-docs`, issue #1123) — the same pairing the
merged refreshes #2363/#2474/#2509 carried, and exactly what CI flagged on the first #2566
attempt (`check-docs`: "this branch changes docs/ARCHITECTURE.md but adds no
agent-wiki/<stem>.md note"). The bot never merges and never pushes to `main`; PR #2566
closes issue #2565.
