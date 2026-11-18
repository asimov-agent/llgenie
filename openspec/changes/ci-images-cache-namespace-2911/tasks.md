# Tasks: ci-images cache refs keyed to image content

- [x] `cache_ref(name, root)` derives `llgenie/<name>:<tag>-buildcache` from the same `tag()` content hash the image ref carries (scripts/ci_images.py)
- [x] `publish` probe + `--cache-from` and `_buildx_push` `--cache-to` pass the root so all three use the keyed ref (scripts/ci_images.py)
- [x] Existing pinned assertions in tests/test_ci_images.py moved to the content-keyed form (3 asserts updated, not duplicated)
- [x] New hermetic test `test_cache_ref_follows_the_image_content`: same content replays, changed lockfile moves the namespace
- [x] Targeted module green: pytest tests/test_ci_images.py rc=0 (42 passed)
- [x] Full hermetic gate green on this tree: `make test-unit` rc=0 (4038 passed, 13573 deselected, 0 failed), including the new `tests/test_ci_images.py::test_cache_ref_follows_the_image_content`
- [x] Fast gates green: lint rc=0, check-wiring rc=0, check-docs rc=0, openspec validate rc=0
- [x] Batch committed and pushed, PR opened closing #2911 with body/commit/issue mirrors aligned
