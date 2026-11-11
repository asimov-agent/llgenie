# Tasks

- [x] 1. OpenSpec change: `proposal.md`, `specs/ci-security-images/spec.md`, this checklist
- [x] 2. `.github/workflows/security-images.yml`: schedule (03:49 UTC) + path-filtered push + workflow_dispatch, never a pull_request; guard job; `packages: write` on the build job only
- [x] 3. `.github/workflows/ci.yml`: delete the `scanner-images` job and its comment block
- [x] 4. `scripts/scanner_image.py`: replace `ci()` with `published(ref)` + `ensure(scanner="all", force=False)`; rewire the CLI; `publish` honors `FORCE`
- [x] 5. `scripts/security_scan.py`: `ensure_image` delegates to `scanner_image.ensure` (no own `docker build`)
- [x] 6. `Makefile`: `ci-security-images` + `security-images-ensure` targets, `.PHONY` and `##` help updated
- [x] 7. `scripts/ci_scope.py` JOBS and `scripts/check_main_ruleset.py` REQUIRED_CONTEXTS drop `scanner-images`
- [x] 8. Tests: `tests/test_scanner_images.py` ensure/single-path/workflow tests; `tests/test_security_scan.py` delegation tests; `tests/test_ci_scope.py` and `tests/test_ci_verdict.py` fixtures/counts updated; `tests/fixtures/main-ruleset-*.json` updated
- [x] 9. Docs: `docs/SCANS.md`, `docs/SCANNERS.md`, `docs/BOTS.md` dispatch table, `docs/changes.d/` index row, `agent-wiki/2026-11-11-ci-security-images.md`
- [x] 10. Final gates green: `openspec validate ci-security-images` ("is valid"), `python3 scripts/scanner_image.py check all` (OK), `scripts/check_wiring.py check` (OK 374 targets), `scripts/check_dispatch_forms.py check` (OK 32 dispatchable), `scripts/check_docs.py check` / `changes_index.py check` (OK 782 fragments), `scripts/check_workflows.py check` (OK) — plus the six touched unit suites (scanner_images, security_scan, ci_scope, ci_verdict, check_main_ruleset, semgrep_rules) pass 179 tests, and `workflow-run-exemptions.json` records the new pipeline's dispatch-red routing decision.
