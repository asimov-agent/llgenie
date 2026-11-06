# vllm-cuda base-stage-hermetic regression guard (#1832)

**Issue:** #1832 — vllm cuda build failure reds every producer at any head, blocking the #1696 runtime bind.

## What was verified against the spec

Spec: `openspec/changes/engine-vllm-cuda-base-stage-hermetic/specs/engine-vllm-cuda-base-stage-hermetic/spec.md`.

The underlying vllm-cuda failure was a **cross-invocation base pull**: on the docker-container buildx
driver a base left by a previous buildx invocation is unresolvable by a later `FROM <base>`, so a bare
`llgenie/base-cuda:<sha>` was pulled from docker.io and denied `insufficient_scope` (run 41971301136 @
84e9684ca2). Issue #1753 fixed the production path (`_combine_base_stage` builds the backend base as an
internal stage) — present in origin/main, the #1696 head `321dabc826`, and the anchor `ea0b9033`. This
change adds the missing regression tests so the fix is locked: no bare base `FROM`, no `docker.io`,
exactly one `AS llgenie-base` per derived cell, across every REAL committed engine Dockerfile.

## Decisions taken

- The production code is already correct (#1753); the gap was **coverage**, so the deliverable is a
  hermetic regression guard, not a code change.
- The tests sweep every `containers/engines/dockerfiles/*/Dockerfile.<arch>` that `FROM`s a backend
  base, so any future param/Dockerfile change that reintroduces the registry pull is caught at unit
  time, not rediscovered as a red cell.
- vllm/cuda is pinned by name so the specific blocker cell has a named test.

**Gates:** `tests/test_engine_image_matrix.py` — 24 passed (21 existing + 3 new) in the `llgenie/test`
container at the head. No workflow/params/product-code change; no gate weakened.
