# Tasks — openspec-presence-gate

- [x] 1. `scripts/check_pr_hygiene.py`: add `openspec_change_findings()` + the bot-gated `pr_openspec_change_findings()` and the `openspec-change` subcommand (mirroring `sync-line`), reusing `_git` / `is_bot_pr` and the live-body plumbing; no new subprocess site.
- [x] 2. `Makefile`: add `check-pr-openspec-change` with a `##` help line and register it in `.PHONY`.
- [x] 3. `.github/workflows/ci.yml` + `.github/workflows/scope.yml`: run `make check-pr-openspec-change` with the same live-body env as `check-pr-sync-line`.
- [x] 4. `openspec/changes/openspec-presence-gate/`: proposal.md + spec.md + tasks.md authored, all task boxes above ticked on verification.
- [x] 5. Prove red-on-old / green-on-fixed: against the pre-fix `check_pr_hygiene.py`, an openspec-empty implementing PR (a scripts+tests change) is NOT flagged (the defect — passes today); against the fixed script it IS flagged; the exemptions (own change added, `OPENSPEC:` body-named, pure docs, human-only) stay green. The test file imports `check_pr_hygiene` through the ONE root (`from scripts import …`, issue #796) so the import-roots ratchet stays green (measured: `check-import-roots ratchet` OK, 12 tests pass).
- [x] 6. `docs/BOTS.md` row + `docs/changes.d/2026-11-05-openspec-presence-gate.md` + `agent-wiki/2026-11-05-openspec-presence-gate.md`; `make changes-index` regenerates CHANGES.md.
- [x] 7. `make check-workflows check-wiring check-docs lint openspec-validate-all openspec-tasks-check` and the new tests pass; `make openspec-validate NAME=openspec-presence-gate` exits 0.

