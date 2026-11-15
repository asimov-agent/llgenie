# Makefile images-domain split: mk/images.mk (issue #2678, PR #PRNUM)

## What was verified

The last unclaimed cluster of the #800 residual: the image build/publish targets moved out of
the top `Makefile` into `mk/images.mk` byte-identically, following the tests-split playbook
(#2677) on top of the #2456–#2461 domain pattern.

- **Moved (9):** `test-image`, `test-image-pull`, `test-variant-image`, `publish-ci-images`,
  `publish-agent-image`, `agent-image-push-check`, `agent-image`, `agent-image-pull` — the
  eight the issue names — plus `agent-image-ref`. The issue's membership note decides by
  RECIPE, not name: `agent-image-ref`'s recipe is `python3 scripts/ci_images.py latest agent`,
  image-shaped, so it moved here instead of the agents sibling (#2676), as the issue
  pre-authorizes.
- **Stayed:** `ci-image-refs` (already `mk/ci.mk`, ci domain — not re-moved), `test-clean`
  (long inline program — #2675's criterion-5 domain), `VARIANT_IMG`/`VARIANT_RUN` variables
  and all banners (the six sibling domain files declare zero variables), every `.PHONY` line.
- **Parity measured at head (rebased onto `d43b1df8b4`, the tip after #2677 landed):**
  `make -qp` sorted-unique target inventory 578 → 579, the sole diff line the
  `mk/images.mk:` include record; `make help` byte-identical to the base (`cmp` clean,
  59 lines); the moved blocks are byte-for-byte the
  source ranges (extracted by line range, not retyped); top `Makefile` 837 → 805 lines — a
  decrease, legal under the #2674 ratchet (ceiling 977); `mk/images.mk` 38 lines, well under
  the 600 ceiling; declared-target grep on the top `Makefile` 90 → 81, a drop of exactly 9.
- **Pinned:** `tests/test_makefile_images_mk_split.py` (8 tests): existence + include, exact
  9-target roster with no extras, `##` help lines kept, zero dual declarations (the #2674
  gate class), no re-declaration in any other domain file, `ci-image-refs` stays in `mk/ci.mk`,
  variant variables stay at the top, `.PHONY` still names the image targets.

## Key decisions

- Recipe-shape membership (the issue's own rule) moved `agent-image-ref` out of the agents
  sibling — #2676's roster is therefore 30, not 31.
- The split is targets-only, matching all six existing `mk/*.mk` files (zero `VAR :=`).

## Current status

OpenSpec change `makefile-images-mk` validated; `make check-wiring`, `make check-docs`,
`make openspec-validate`, `make openspec-tasks-check` green at head; full `make test-unit`
green. Order respected: this lands before the #2675 extraction, and the tests split (#2677)
touches a disjoint target set.
