# tag-identity-repin-gate

## Why

Merged as main `aa700cf27` (PR #2517), a change touched 36 engine Dockerfiles and NO params file.
The published tag `<pin8>-<hash8>-<variant>` hashes the Dockerfile bytes
(`scripts/engine_image.py::_image_inputs`), so every engine image tag identity on main moved while
the merge gate (`repinned_engine_ids`) and the pre-merge publisher (`engine-build-pr-trigger` →
`engine_build_trigger.py`) — which both diff the params FILE only — saw an empty diff. The PR merged
without publishing anything: all 28 committed engine x arch tags became unpublished (404 on the exact
tags `make install` pulls), main CI has been red since (`linux / unit` run 43149489329: 1 failed /
3629 passed; `registry-liveness` run 43149489162: 28/28 pins unpublished). Issue #2559.

## What Changes

- Add `retagged_engine_ids` to `scripts/check_engine_pins_published.py`: for every buildable
  engine x arch cell, compare the tag this tree would publish (`engine_image._current_tag`) with the
  tag `base` would publish (`engine_image._tag_at`); name every engine whose cells differ, and every
  engine with no base copy (first import).
- `repinned_engine_ids` becomes the union of the params-file diff (behaviour unchanged, never
  loosened) and the tag-identity diff.
- The will-arm (`scripts/engine_build_trigger.py`, already a consumer of `repinned_engine_ids`) and
  the may-arm (`check_engine_pins_published` itself) inherit the shared diff automatically: a
  retagging PR dispatches scoped `engine-build push=true` builds for exactly its retagged engines,
  and cannot merge until those exact tags resolve.
- `tests/test_ci_publish_order.py::_deferred_engines` replaces its `scripts/engine_image.py`-only
  special case (issue #823) with the same helper: retagged engines are deferred to
  `make ci-wait-engine-images` on a moving base; base == head defers nothing.
- No `.github/workflows/*.yml` changes. `registry-liveness`'s self-remediation (issue #2259) stays
  as the post-merge safety net, not the only line of defence.

## Impact

- Affected spec: `tag-identity-repin-gate` (ADDED requirements)
- Affected code: `scripts/check_engine_pins_published.py`, `tests/test_ci_publish_order.py`
  (`scripts/engine_build_trigger.py` consumes the shared diff unchanged)
- Affected tests: `tests/test_check_engine_pins_published.py` (new fixture tests),
  `tests/test_engine_build_trigger.py` (monkeypatches the same seam already)
- Issue: #2559. Related: #2517 (the merged retag), #2518, #2529, #2259, #1633, #823.
