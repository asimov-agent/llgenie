# Tasks: scanner-rules-capture-provenance (#2713)

## 1. The keep
- [x] 1.1 `scripts/scanner_image.py::write()`: read the prior record before stamping; keep the committed `rules_captured_at` while the recomputed `rules_sha` matches, stamp today only on a moved/never-recorded pack

## 2. Tests
- [x] 2.1 `tests/test_scanner_images.py`: `_semgrep_tree` fixture (semgrep scanner + rules pack)
- [x] 2.2 `test_rewriting_an_unchanged_rules_pack_keeps_the_capture_date`
- [x] 2.3 `test_a_changed_rules_pack_advances_the_capture_date`

## 3. Verification
- [x] 3.1 `make check-scanner-images` and `make check-security-scan` green with the new seam
- [x] 3.2 `make openspec-validate NAME=scanner-rules-capture-provenance` passes
