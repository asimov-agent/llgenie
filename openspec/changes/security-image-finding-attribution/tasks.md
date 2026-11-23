# Tasks — security-image-finding-attribution

Issue: [#3036](https://github.com/asimov-agent/llgenie/issues/3036)

- [x] 1. OpenSpec change (`make openspec-new NAME=security-image-finding-attribution`) + issue #3036 filed through `issue_body.render` with the six sections and its out-of-scope items pointing at their own issues (#2967, #2836/#2935, #2518-vs-#2609).
- [x] 2. `scripts/security_scan.py::scan_image`: write `image-<slug>.meta.json` for the validated digest-pinned ref BEFORE the trivy/Syft/Grype chain runs.
- [x] 3. `scripts/security_scan.py::findings`: refuse an `image-*.trivy.json` / `image-*.grype.json` whose `image-<slug>.meta.json` is missing or names no ref — name the report, emit nothing from it.
- [x] 4. `scripts/security_scan.py::image_owner(ref)`: map a scanned ref back to its `containers/scanned-images.json` entry (direct `ref` match, `engine`+`variant` match through `_resolve_engine_ref`) and return its `owner`.
- [x] 5. `scripts/security_issues.py::body_for`: image findings get the image remediation (ref + allow-list owner, or the plain statement that the allow-list names no owner) and never the `tools/requirements*.in` → `requirements*.txt` path.
- [x] 6. `scripts/security_issues.py::set_labels`: after POST + read-back, delete the `component:*` labels the finding no longer earns and prove the removal.
- [x] 7. Tests: `test_image_meta_survives_a_mid_scan_failure`, `test_an_image_report_without_its_meta_fails_the_run`, `test_image_owner_names_the_allow_list_entry_and_its_owner` (scan); `test_an_image_finding_names_the_image_owner_not_the_pin_path`, `test_a_relabelled_finding_loses_its_stale_component_label` (issues); existing image-finding/pin-path tests updated, none deleted.
- [x] 8. `agent-wiki/2026-11-23-security-image-finding-attribution-3036.md` + `docs/changes.d/` fragment, `make changes-index` regenerated.
- [x] 9. Verification tickable at the done-claim: `make openspec-validate NAME=security-image-finding-attribution` rc=0, `make check-docs` rc=0, full `make test-unit` green at this head with zero skips (UNIT_RC=0), `make lane-preflight` printing `preflight: OK`, and `make security-scan-fixture` (report-only image scan) still producing its known-vulnerable fixture findings at this head.
