# tag-identity-repin-gate

## Why

The pin-bump merge gate (`check_engine_pins_published`) and the pre-merge
publisher (`engine_build_trigger`) both diff the params FILE only to decide which
engines a change "repinned". But the published image tag
`<pin8>-<hash8>-<variant>` hashes the params file AND the engine's
`Dockerfile.<variant>` plus `entrypoint.sh` + `engine_runner.py`
(`engine_skills._image_inputs`). So a Dockerfile-only change — the #2517 shape:
36 Dockerfiles touched, an EMPTY params diff — re-tags every engine image with a
diff that reads as "no engine repinned". The gate saw an empty diff, the PR
merged without publishing anything, and the 28 committed engine×arch tags main
points at are all unpublished (they 404 in GHCR). Main CI has been red since:
`linux / unit` run 43149489329 (`test_every_image_install_pulls_is_published`,
1 failed / 3629 passed) plus the scheduled `registry-liveness` and `ci-hf-live`
runs. A gate that reads tag identity only AFTER the merge that moved the tags is
not a gate.

## What changes

1. A shared tag-identity diff in `scripts/check_engine_pins_published.py`:
   `retagged_engine_ids(base)` — for every buildable engine×arch cell it compares
   the tag this tree would publish (`engine_image._current_tag`) with the tag
   `base` would publish (`engine_image._tag_at`) and names every engine whose
   cells differ; an engine with no base copy (first import) counts too.
2. `repinned_engine_ids` becomes the UNION of the params-file diff (unchanged,
   never loosened) and the tag-identity diff. Both consumers inherit
   automatically: the may-arm merge gate blocks a retagging PR until its exact
   tags resolve in GHCR, and the will-arm `engine_build_trigger` dispatches scoped
   `push=true` builds for exactly those engines — the PR that retags an image is
   the PR that publishes it.
3. The unit suite's deferral (`tests/test_ci_publish_order.py::_deferred_engines`)
   replaces its `engine_image.py`-text and per-Dockerfile text special cases with
   the same shared tag-identity helper: a retagging PR defers retagged engines to
   `make ci-wait-engine-images`, and a main run (base == head) still checks every
   tag.
4. `registry-liveness` self-remediation (#2259) stays as the post-merge safety
   net but stops being the only line of defence.

No `.github/workflows/*.yml` changes.

## Out of scope

- The 28 `engine-build` remediation dispatches already in flight on main (the
  #2259 self-dispatch) — tracked as the acceptance criteria under "affected:
  main is red"; not this PR's code.
- #2529 (post-#2517 engine-build sweep), #2518 (fork-head publish deadlock) —
  separate issues.
