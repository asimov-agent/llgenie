# Tasks

- [x] 1. `scripts/scanner_image.py` gains `_published_platforms(ref)` — `docker buildx imagetools inspect` via `scripts/proc.py::run_ok`, rc≠0 → empty set (never an exception). Verified: targeted `pytest tests/test_scanner_images.py` 12 passed (host venv, 2026-11-10); proven again by `ci-unit` at the PR head
- [x] 2. `publish()` probes first: all required platforms present → prints a skip line naming the ref and returns 0 without a `--push`; tag absent or a platform missing → the `--push` runs unchanged. Verified: `test_an_already_published_tag_is_not_re_pushed`, `test_a_tag_missing_a_required_platform_still_publishes`, `test_a_tag_absent_from_the_registry_publishes_as_today`
- [x] 3. A failed `build()`/`publish()` prints the command's exit code and a bounded tail of its captured stdout+stderr (issue #2452 criterion 4), keeping the non-zero exit. Verified: `test_a_failed_publish_prints_its_captured_streams`, `test_a_failed_build_prints_its_captured_streams`
- [x] 4. `tests/test_scanner_images.py` extended: skip path, missing-platform negative control, absent-tag control, failure-streams assertion — all with a faked probe/push, no real Docker. Verified: 5 new tests, module 12 passed 2026-11-10
- [ ] 5. `make test-unit` green at the head with the extended module; `make check-scanner-images` still passes on the real tree (measured rc=0 2026-11-10: `[scanner-image] OK: 3 scanner image(s) pinned…`)
- [x] 6. `make openspec-validate NAME=scanner-image-publish-idempotence` exits 0. Verified: "Change 'scanner-image-publish-idempotence' is valid" rc=0
- [ ] 7. Docs trio in the same PR as the change: `agent-wiki/2026-11-10-issue-2453-scanner-image-publish-idempotence.md`, `docs/changes.d/` fragment, `CHANGES.md` row — each naming #2453 and the PR
- [ ] 8. `make lane-preflight` prints `preflight: OK` at the pushed head; one ready-for-review PR closing #2453; #2452 implemented (criteria 1/3/4) but NOT closed, recorded on the #2452 thread
