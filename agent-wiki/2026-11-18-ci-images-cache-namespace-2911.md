# ci-images helper cache refs keyed to image content (issue #2911)

## What was verified

Issue #2911 was filed out of the #2891 lane: the engine-cell/base cache refs were keyed
to content there (PR #2912), but the helper-image seam — `scripts/ci_images.py::cache_ref` —
still returned the fixed `llgenie/<name>:buildcache` for every helper image, so any
Dockerfile/lockfile change replayed the buildx registry cache against a namespace
unrelated to the content being built.

This lane keys the helper refs to the same content hash the pushed tag carries
(OpenSpec change `ci-images-cache-namespace-2911`):

- `cache_ref(name, root)` now returns `llgenie/<name>:<12hex tag>-buildcache`, reusing the
  exact `tag(name, root)` hash `ref(name, root)` publishes.
- `publish` probes/reads that keyed ref for `--cache-from` (only when it exists) and
  `_buildx_push` exports `--cache-to` to it; both pass the repo root through.
- The three assertions in `tests/test_ci_images.py` that pinned the fixed name were moved
  to the content-keyed form (updated, not duplicated), and a new hermetic test
  `test_cache_ref_follows_the_image_content` pins unchanged-replay and
  changed-content-moves-namespace.

## Key decisions

- No new Makefile target: the unit suite is DISCOVERED (`scripts/unit_tests.py`), so the
  new test rides `make test-unit`; the ci-images publish lane runs the same script, so the
  registry effect lands without workflow changes.
- Cache WRITE policy and the probe-before-read behaviour (issue #178 cold-cache fix)
  are untouched: only the namespace derivation changed.

## Current status

Implementation and hermetic tests are done in this change; the proof chain (unit gate on
the final head, ci-images lane green, landing stamp on the issue) is tracked on the issue
and its PR.
