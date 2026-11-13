# scanner-digest-pin — tasks

- [x] 1. `containers/scanners/digests.json` carries a `digest` per scanner ref, filled from the
       registry index digests CI publishes. Verified: read the file back; each of grype/semgrep/trivy
       has a `sha256:<64 hex>` `digest` (grype `12ef938b…`, semgrep `180c3f7e…`, trivy `88490910…`,
       measured via `docker buildx imagetools inspect`), and `test_every_scanner_records_an_immutable_digest`
       asserts it.
- [x] 2. `scripts/security_scan.py` resolves the actual digest of the image it would run and refuses
       (exit non-zero, naming BOTH digests) when it differs from the recorded one; a missing or
       malformed recorded digest also reds. Verified: `test_verify_digest_refuses_a_mismatch` (the
       injected negative control raises `SystemExit` naming both) and `test_check_reds_a_scanner_without_a_digest`.
- [x] 3. Every scan run states the executed scanner digest in its output. Verified:
       `test_verify_digest_names_the_matching_digest` asserts the executed digest is printed; the live
       `verify_digest('semgrep')` prints `executing scanner image digest sha256:180c3f7e…`.
- [x] 4. `scripts/scanner_image.py::write` (`make scanner-digests`) records the per-scanner `digest`
       alongside `version`/`tag`/`ref`. Verified: `test_write_records_the_published_digest` asserts a
       `digest` after `write()`; `test_a_digestless_digests_file_fails_check` proves `check()` reds a
       missing digest.
- [x] 5. Tests lock the behaviour (no business logic mocked, digests read from the real tree):
       `tests/test_security_scan.py` and `tests/test_scanner_images.py`. Verified: the two modules run
       green (61 passed via `python3 -m pytest tests/test_security_scan.py tests/test_scanner_images.py`).
- [x] 6. `make check-security-scan` and `make check-scanner-images` pass on the real tree. Verified:
       both exit 0 with the digests recorded (`[security-scan] OK: …3 pinned scanner refs…` /
       `[scanner-image] OK: 3 scanner image(s) pinned…`).
- [x] 7. Docs in the same change: `agent-wiki/2026-11-13-scanner-digest-pin-2609.md` + one row in
       `docs/changes.d/2026-11-13-scanner-digest-pin-2609.md` naming the issue and this change.
       Verified: `make check-docs` exits 0.
- [x] 8. Host-side gates green and the OpenSpec change well-formed. Verified: `make lint`,
       `make check-wiring`, `make openspec-tasks-check NAME=scanner-digest-pin` all exit 0; the change
       mirrors the schema of valid active changes (proposal.md + specs/…/spec.md + tasks.md +
       `.openspec.yaml`). The dockerized `make openspec-validate NAME=scanner-digest-pin` runs in the
       PR's `ci-openspec` job (no container runtime in this sandbox).
