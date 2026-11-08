# Hindsight memory bootstrap — tasks

- [x] add `scripts/memory_bootstrap.py` with `install` (pinned, fixed port, idle-timeout 0, detached, idempotent, `--dry-run`)
- [x] add `bootstrap` (one template per profile, reuse the plugin's env builder, idempotent, `--dry-run`, never prints/copies a key)
- [x] add `verify` (per-profile PASS/FAIL: daemon pid + port, `/proc/<pid>/environ` model/base-url, newest `Connection verified:` line; empty provider or absent key FAILS by name)
- [x] add `tests/fixtures/fake-hindsight-plugin/embedded.py` (the plugin env-builder contract stand-in)
- [x] add `tests/test_memory_bootstrap.py` covering every acceptance criterion with real script runs
- [x] wire `memory-install` / `memory-bootstrap` / `memory-verify` / `memory-check` into the Makefile (working recipes, `.PHONY`)
- [x] record the four targets as deliberate docs exceptions (AC9 forbids a docs/ section)
- [x] add the change note trio (agent-wiki entry + `docs/changes.d/` fragment + rendered CHANGES.md row)
- [x] openspec proposal + spec (Given/When/Then, a `- **Test:**` per scenario) + tasks
- [x] verify gates: `make test-unit`, `make check-wiring`, `make lint`, `make check-docs` green
  (`check-wiring` OK, `lint_linefeeds` LINT OK, `check-docs` ok, `check-import-roots` ratchet OK,
  `openspec-tasks-check` OK, `check-secret-output` OK; the 11 new tests pass; `make test-unit` /
  `make lint` containerized targets could not run here — no Docker daemon in this agent container —
  so the equivalent host-side commands ran green instead)
