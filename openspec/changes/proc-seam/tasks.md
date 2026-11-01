# Tasks

- [x] 1. `scripts/proc.py` exists with exactly three named policies — `run_text()` (stdout, raises on non-zero), `run_ok()` (rc/stdout/stderr, never raises), `run_checked()` (raises naming command + stderr), no defaults — and `make check-wiring` / `make ci-unit` runs its tests
- [x] 2. `scripts/detect_server.py` and `scripts/engine_skills.py` no longer return `""` for a failed command: a probe whose command exits non-zero is reported as a failure, with a test that runs a command exiting 1 on the binary path and asserts the loud outcome
- [x] 3. `scripts/detect_server.py` `_run` is migrated to the seam (no `""` return), with the loud-failure test
- [x] 4. `scripts/engine_skills.py` `_run` is migrated to the seam (no `""` return), with the loud-failure test
- [ ] 5. Every one of the 11 no-exit-code wrappers is gone: each call site either states its policy (via `proc.*` or `# proc-allow:`) or is deleted, keeping every existing message and exit code identical
- [ ] 6. The 16 checking wrappers collapse onto `run_checked()`, keeping every existing message and exit code identical
- [ ] 7. A gate exists: inside `scripts/`, `subprocess.run`/`check_output`/`Popen` are allowed only in `scripts/proc.py` or on a line carrying `# proc-allow: <reason>`, checked from `make ci-unit`, proven by a test that a new bare `subprocess.run` in `scripts/` reds the gate
- [ ] 8. A `# proc-allow:` census is printed by `make ci-unit` (or a report target), naming the remaining direct call sites as a shrinking number
- [ ] 9. OpenSpec validates: `make openspec-validate NAME=proc-seam` exits 0
- [ ] 10. Docs updated: `agent-wiki/2026-11-01-issue-797-proc-seam.md` change note + `docs/changes.d/` fragment + `CHANGES.md` row; the PR body carries `closes #797`
- [ ] 11. Gates green: `make lane-preflight` / `make test-unit` and the `ci-unit` composite at the pushed head
