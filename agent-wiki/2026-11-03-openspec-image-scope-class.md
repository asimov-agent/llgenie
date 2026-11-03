# An openspec-image change must run `ci-images`, not skip `ci.yml` (issue #1657)

`openspec/Dockerfile` builds the OpenSpec CLI image, whose hash is published by exactly one CI job:
`ci-images` (`scripts/ci_images.py` hashes `openspec/Dockerfile` alone). It used to be classed `docs`
via the `openspec/**` glob, so a pull request whose only touch was that file never started `ci.yml` at
the trigger (`pull_request.paths-ignore` lists `openspec/**`), and the `ci-images` job — the sole
publisher — never ran. `scope.yml`'s docs gate `make openspec-image-pull` then failed on the
unpublished hash, so no `openspec/Dockerfile` content change could merge (the image only publishes on a
post-merge main push, which the red PR can never reach).

The fix classifies `openspec/Dockerfile` with the `containers` family (the same class the test image
`containers/test/Dockerfile` already uses), keeps the OpenSpec spec documents (`openspec/changes/**`,
`openspec/config.yaml`) as `docs`, and moves `ci.yml`'s `paths-ignore` in lockstep — the trigger list
is asserted exactly by `tests/test_ci_scope.py::test_ci_yml_ignores_exactly_the_docs_trigger_list`, so
the workflow and the classifier cannot drift. A regression test proves `openspec/Dockerfile` now
selects the `containers` class and the `ci-images` job, while the spec documents stay `docs`.
