# Tasks

- [x] Scope the `concurrency.group` key in `.github/workflows/engine-build-pr-trigger.yml` to `${{ github.event.pull_request.number }}-${{ github.event.pull_request.head.sha }}`, preserving `cancel-in-progress: false`.
- [x] Confirm the change is confined to the trigger workflow's `concurrency` block (no `engine-build.yml`/producer guard/gate change).
- [x] `make check-workflows` green (workflow YAML well-formed); the package unit suite stays green.
- [x] Docs trio per #1123: `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` regenerated.
- [x] PR opens `closes #1831`; normal review flow (#1644 acceptance write-back, owner merges).
