# Change: Split the image build/publish targets out of the top Makefile into mk/images.mk

## Why

Issue #2678 (residual of #800, one-issue-per-make-file rule): the top Makefile still declares
the image build/publish cluster — the supply-chain half of the build (the images every CI job
and every agent lane runs in). Re-pin PRs touch `test-image`/`test-variant-image`, fleet PRs
touch `publish-*`, and every such edit drags the monolith. This completes the domain pattern of
`mk/engines.mk` (#2456), `mk/gates.mk` (#2457), `mk/ci.mk` (#2458), `mk/security.mk` (#2459),
`mk/install.mk` (#2461) and `mk/bots.mk` (#2460) for the images domain, following the same
byte-identical-move playbook proven by the tests split (#2677, PR #2695).

## What Changes

- **Moved (9 targets, recipes and `##` lines byte-identical):** `test-image`,
  `test-image-pull`, `test-variant-image`, `publish-ci-images`, `publish-agent-image`,
  `agent-image-push-check`, `agent-image`, `agent-image-pull`, plus `agent-image-ref` — the
  issue's membership note decides by RECIPE, not name: `agent-image-ref`'s recipe is a
  `scripts/ci_images.py` call (image-shaped), so it moves here instead of the agents sibling
  (#2676), as the issue itself pre-authorizes ("if its recipe turns out image-shaped, move it
  here instead and say so in the PR").
- **Stayed:** `ci-image-refs` (already in `mk/ci.mk`, the ci domain — not re-moved),
  `test-clean` (container hygiene for the test image but a long inline program — #2675
  criterion-5 territory), the `VARIANT_IMG`/`VARIANT_RUN` variables and banners (all six
  existing domain files hold zero variables: the split convention is targets only), every
  `.PHONY` line (top Makefile, per the #2456–#2461 precedent).
- `include mk/images.mk` appended to the include block after `mk/bots.mk`.
- New test module `tests/test_makefile_images_mk_split.py` pins the split (membership,
  byte-identity of every moved block against `origin/main`, zero dual declarations, help
  identity).
- `docs/ARCHITECTURE.md` `mk/` table gains the `images.mk` row; CHANGES.md/docs/changes.d row
  in the same commit.

No behavior changes: no recipe line changes, no new targets, no deletions.

## Impact

- Affected specs: `makefile-split` (residual closure under #800)
- Affected code: `Makefile`, `mk/images.mk` (new), `tests/test_makefile_images_mk_split.py`
  (new), `docs/ARCHITECTURE.md`, `docs/changes.d/`, `agent-wiki/`
