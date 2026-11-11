# Tasks

- [x] 1. `openspec/changes/file-hygiene-gate` — proposal + `specs/file-hygiene-gate/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist
- [x] 2. `.gitignore` — blanket `*.log` rule plus a dot-prefixed `.<word><digits>.<ext>` scratch rule; `git check-ignore` confirms a new `.foo.log` is ignored and `.env.example` stays trackable
- [x] 3. `git rm .unit2.log .pr874.md` (forward removal, no history rewrite); both absent from `git ls-files`
- [x] 4. `scripts/check_file_hygiene.py` — scans `git ls-files`, refuses `*.log` and dot-scratch artifacts, honours a dated exception fixture, fails a stale/malformed exception, lists findings as paths only
- [x] 5. `tests/fixtures/file-hygiene-exceptions.json` — dated allowlist fixture (starts empty)
- [x] 6. `Makefile` — `check-file-hygiene` + `file-hygiene-report` targets (## help, declared `.PHONY:`), `$(MAKE) check-file-hygiene` in `ci-unit`
- [x] 7. `scripts/issue_bot_gates.py` — `check-file-hygiene` added to `FAST_GATES` so `make lane-preflight`/issue-bot-gates reach it
- [x] 8. `tests/test_file_hygiene.py` — real-git tests for every spec scenario plus the Makefile/FAST_GATES/.PHONY wiring
- [x] 9. `README.md` — `check-file-hygiene` and `file-hygiene-report` documented next to the other check gates
- [x] 10. `agent-wiki/2026-11-11-file-hygiene-gate.md` + `docs/changes.d/2026-11-11-file-hygiene-gate.md` — the work record and its index row (issue #2484)
- [x] 11. Verified: `make check-file-hygiene`, `make check-wiring`, `make issue-bot-gates-check`, `make check-empty-files` all exit 0; `tests/test_file_hygiene.py` all pass (direct pytest; the full `make test-unit` and `make lint` need the docker test image, which is unavailable on this bare host — reported, not faked)
