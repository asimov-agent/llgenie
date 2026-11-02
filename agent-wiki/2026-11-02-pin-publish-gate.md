# A pin-bump PR may not merge until its image is published (issue #1622)

A bump PR used to publish the engine image it moved in the SAME CI run: `ci.yml`
built and pushed the new tag in its parallel `engine-image-*` jobs, and
`tests/test_ci_publish_order.py::test_every_image_install_pulls_is_published` could
DEFER the repinned engine because the producing cell was that very run. Since issue
#1027 no engine is built or published by the PR pipeline at all — building and
publishing is the engine-build PRODUCER's job, and it happens only when that producer
is dispatched with `push=true`.

Nothing else verified the image at the PR. A pin bump could therefore merge to main
with its new tag never appearing on GHCR, and the failure stayed hidden until a later
scheduled run tripped on the manifest 404 — the #1365/#1587 recurring class (e.g.
#1517 bumped litert, built OK in a local engine-build run, but was never dispatched
`push=true`, so ghcr never received the `:pin-params-arch` tag).

## What changed

- `scripts/check_engine_pins_published.py` (new): `repinned_engine_ids(base)` finds
  engines whose COMMITTED params differ from the base ref (resolved by scripts/base_ref,
  issue #925) or are new there — the engines this change actually moves, from the params
  file a bump writes, never a skill. `check(base)` then takes each repinned engine's
  exact image tag from the ONE tag formula (`engine_image.resolve().tag`, the same list
  `make install` pulls), probes the registry manifest for it (`engine_image._digest_http`,
  the hermetic-testable probe `wait_published` uses, issue #169), and reds on a 404 /
  absent manifest, naming the exact ref; green only when every repinned engine's tag
  resolves. Nothing is pulled or built; no container starts. An engine this change does
  NOT re-pin is never queried, so a normal PR stays hermetic and fast — the network is
  touched only for engines a bump actually moved. `LLGENIE_REGISTRY` overrides the
  registry (a fork's GHCR), matching every other engine path.
- `make check-engine-pins-published` (+ `engine-pins-published-report`), wired into
  `ci-unit` (the PR pipeline) and `.PHONY`. Because it is a ci-unit step, no workflow
  file changes shape and the no-skipped-job / one-target-per-job guards are untouched.

## Why a diff-only gate cannot be weaker

The image a bump moves is the one `install` pulls and engine-build publishes. A gate
that merely re-checks launcher tags or the committed-params list cannot see publication
— only a registry manifest digest can. The gate is therefore scoped to the exact tags
`install_plan` resolves, deferred to nothing: the whole point is that publication is
producer-only now, so a bump must wait for a `push=true` dispatch before it may merge.

## Out of scope

No re-pin or retroactive publish of historical images; no change to pin values; the
engine-build producer's own publish flow is unchanged.
