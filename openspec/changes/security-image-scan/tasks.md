# Tasks — security-image-scan (issue #2706)

- [x] 1. `scripts/security_scan.py`: `scan_image(ref, slug)` (digest-enforced, reports-dir mount), `resolve_scan_targets()` registry-digest resolver, `scan_images_all()`, `scan_published_image()`, `scan_image_fixture()`, meta records, `findings()` image-report pickup with ref tagging, `check()` manifest validation, CLI `scan-image`/`scan-images`/`scan-published`/`scan-fixture`
- [x] 2. `containers/scanned-images.json`: manifest with agent image + a resolved engine entry + fixture ref documented
- [x] 3. `mk/security.mk` + Makefile `.PHONY`: `security-scan-images`, `security-scan-image`, `security-scan-published`, `security-scan-fixture`; `.gitignore` entry for `security-reports-fixture/`
- [x] 4. Workflows: security-scan.yml scan-images + fixture steps between scan-all and verdict; engine-build.yml post-push `security-scan-published` step (continue-on-error) scanning the just-published digest
- [x] 5. `scripts/security_issues.py`: Finding carries the image ref; `component_of` names image findings `component:container`; `## Technical` names the exact `ref@digest`; marker idempotency unchanged
- [x] 6. Tests in `tests/test_security_scan.py` + `tests/test_security_issues.py`: scan_image argv wiring + digest refusal + manifest resolution + unpublished-image hard failure + findings/verdict/tag normalization + fixture loud-failure proof (hermetic)
- [x] 7. Docs: changes.d fragment + agent-wiki entry naming #2706 + ARCHITECTURE census re-measure
- [x] 8. Local proofs: `make security-scan-fixture` rc 0 with findings; `make security-scan-images` rc 0 with parseable reports; `make check-security-scan` rc 0
- [ ] 9. Gates green: `make check-security-scan check-wiring check-workflows check-docs test-unit lane-preflight openspec-validate` on the branch
