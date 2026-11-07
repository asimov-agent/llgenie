# Tasks — pr-acceptance-form

- [x] 1. `scripts/check_pr_hygiene.py`: add `pr_acceptance_form_findings()` (bot-gated via `is_bot_pr`) and the `acceptance-form` subcommand (mirroring `sync-line`), importing `acceptance_writeback.acceptance_items` (reused, never restated, issue #1796); no new subprocess site.
- [x] 2. `Makefile`: add `check-pr-acceptance-form` with a `##` help line and register it in `.PHONY`.
- [x] 3. `.github/workflows/ci.yml` + `.github/workflows/scope.yml`: run `make check-pr-acceptance-form` with the same live-body env as `check-pr-sync-line`, BEFORE the `check-pr-acceptance` step (#1796), for both guard docs.
- [x] 4. `openspec/changes/pr-acceptance-form/`: proposal.md + spec.md + tasks.md authored, all task boxes above ticked on verification.
- [x] 5. Prove red-on-old / green-on-fixed: against the pre-fix `check_pr_hygiene.py`, a bot body with no acceptance checklist is NOT flagged (the defect — passes today); against the fixed script it IS flagged; a human-only range stays green. The test file imports `check_pr_hygiene` through the ONE root (`from scripts import …`, issue #796) so the import-roots ratchet stays green.
- [x] 6. `docs/BOTS.md` row + `docs/changes.d/2026-11-05-pr-acceptance-form.md` + `agent-wiki/2026-11-05-pr-acceptance-form.md`; `make changes-index` regenerates CHANGES.md.
- [x] 7. `make check-workflows check-wiring check-docs lint openspec-validate-all openspec-tasks-check` and the new tests pass; `make openspec-validate NAME=pr-acceptance-form` exits 0.
