# Tasks: rehome-dispatch-only-lanes

- [x] 1. `scripts/check_ci_discipline.py`: add `DISPATCH_ONLY_LANES` (the seven deactivated lanes -> their live driver) and the check: each roster file declares no `on.schedule:` and carries the `# Triggered now (issue #2703):` marker; `report` prints the classification (proven: `make check-ci-discipline` rc=0 on the branch)
- [x] 2. Fix the seven workflow headers: correct the stale "Trigger surface" wording and add the `# Triggered now (issue #2703):` line to architecture-bot, issue-bot, issue-dedupe, issue-refiner, registry-sync-review, search-smoke, rebase-bot (proven: gate marker check green on all seven)
- [x] 3. `tests/test_ci_discipline.py`: roster completeness, marker-missing finding, schedule-re-added finding, live tree green (proven: `pytest tests/test_ci_discipline.py -q` rc=0, 16 passed)
- [x] 4. Docs: `docs/changes.d` fragment + `agent-wiki` entry naming #2703 and the PR; run `make changes-index` (proven: `make changes-index check-docs` rc=0)
- [x] 5. Gates green on the branch: `make check-ci-discipline check-workflows check-wiring check-docs openspec-validate test-unit` rc=0 (proven: local runs on the PR head; CI unit job re-runs the suite on the same head)
- [x] 6. Record the per-lane classification on issue #2703 (issue body stays the goal; the gate's roster is the machine-readable record) (proven: issue #2703 body updated 2026-11-15T23:51:41Z with the per-lane decision, verified by read-back)
