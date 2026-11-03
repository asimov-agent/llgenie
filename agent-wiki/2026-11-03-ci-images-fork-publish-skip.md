# A fork PR's `ci-images` publish skips the write GitHub will never grant (issue #1673)

`ci-images` is the sole publisher of the CI images (`llgenie/test`, `llgenie/openspec`). A
`pull_request` run from a FORK head carries a token scoped to the base repository's GHCR packages
**read-only** — no `permissions: packages: write` in the workflow can change that — so a fork PR
that changes a CI-image Dockerfile produces a NEW hash that GitHub will never let it push. Before
this fix `scripts/ci_images.py::publish()` ran `docker buildx build --push` unconditionally, so the
push was denied after the ~31s multi-arch build, the `ci-images` job redded, and `scope.yml`'s docs
gate `make openspec-image-pull` redded on the unpublished hash — no `openspec/Dockerfile` (or
`containers/test/Dockerfile`) change from a fork could merge.

The engine publish path already solved this (`scripts/engine_image.py::push` + issue #155): inside a
`pull_request` run, the registry's write denial (`WRITE_DENIED`) becomes a loud `::warning` skip
(exit 0) — "the image is built here, the run that lands the change publishes it" — locked by
`tests/test_ci_publish_scope.py`. `publish()` now applies the same contract to CI images: the denied
push is a loud skip, a same-`push`-run denial or any other failure still fails, and
`scope.yml`'s docs gate uses `make openspec-image` (`ensure`: pull the published hash else build the
change's own Dockerfile) instead of a strictly-pull target, so a fork PR whose new hash cannot yet
exist is still validated against its own image rather than red for a write GitHub will never grant.
Regression tests in `tests/test_ci_images.py` drive `publish()` with the literal denial (skip on
`pull_request`, fail on `push`, fail on any non-permission error).
