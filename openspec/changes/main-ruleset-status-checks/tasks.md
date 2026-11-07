# Main ruleset status-checks guard — tasks

- [x] write scripts/check_main_ruleset.py: `check` (fail on missing/under-pinned required_status_checks), `report`, `apply` (scripted PUT), subset + named-drift semantics, `--fixture` offline mode
- [x] pin the required context set from a real merged PR's emitted check-runs (measured, not assumed)
- [x] wire `check-main-ruleset` / `main-ruleset-report` / `main-ruleset-apply` make targets (`.PHONY` + `##` help) and document in docs/BOTS.md
- [x] add the monitor workflow (scheduled consumer, holds.yml pattern) that runs the guard — the missing rule has a visible red
- [x] tests: guard reds the current (two-rule) ruleset, greens a fixture carrying required_status_checks covering the pin, report exits 0, subset floor not an exact match; prove the guard catches the bug before trusting it (run against the missing-rule fixture, then the fixed fixture)
- [x] openspec spec (Given/When/Then with `- **Test:**` refs) + proposal + tasks; `make openspec-validate NAME=main-ruleset-status-checks` passes
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #1400
- [x] one ready-for-review PR closing #1400: `Issue:`/`Fix:`/`Benefit:`/`Technical:`, `AGENTS:` (origin/main sha), green on its own merge-commit re-run
- [x] state on #1400 precisely what remains owner-admin-only (the scripted apply + the live red-BLOCKED verification) so a reader cannot mistake the guard for the mutation
