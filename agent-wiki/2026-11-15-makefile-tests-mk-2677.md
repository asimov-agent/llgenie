# Makefile test-suite domain move to mk/tests.mk (issue #2677, PR #2695)

## What was done

Moved the 18 host/user test-suite targets out of the top `Makefile` into a new
`mk/tests.mk`, appended to the include block after `mk/bots.mk` — the proven
#2456–#2461 playbook, first test-domain residual of #800's residual list.

Targets moved (byte-identical blocks, verified against `HEAD:Makefile`):
`test-env` `test-clean` `test-unit-network` `test-unit` `test-hub-live`
`test-strata-live` `agents-read-venv` `test-agents-read` `test-agent-skills-live`
`test-board-ownership-host` `test-recall-step` `test-top-tier` `test-top-tier-ci`
`test-top-tier-serve` `test-top-tier-serve-ci` `test-top-tier-cli-ci` `test`
`download-test-model`. The `PY312`/`AGENTS_READ_VENV`/`HERMES_AGENT_PIN`/
`AGENTS_READ_STAMP` definitions and the stamp-file rule move **with** the
`agents-read-*` cluster because `agents-read-venv: $(AGENTS_READ_STAMP)` expands
its prerequisite at parse time — the definitions must be defined before it in the
same file.

Boundary kept as the issue draws it: `ci-*` job targets stay in `mk/ci.mk`;
`test-image*`/`test-variant-image` stay for #2678 (images domain); native-engine
targets + `NATIVE_HOST`/`NATIVE_GUARD` stay (not in #2677's 18); `.PHONY` entries
stay in the top file (bots.mk precedent); `test` moves as suite entry point
(#2677: specifier's call), `all` stays.

## Verified against the spec

- `make -qp` target inventory identical before/after at the same content (the only
  new record is the include file's own); `make -qp` rc unchanged (rc=1 is this
  repo's baseline for that command, same on pristine main).
- Top `Makefile`: 76 → 58 declared targets (−18 exactly, zero added),
  977 → 837 lines. `mk/tests.mk`: 130 lines, 18 targets.
- All 15 moved block ranges byte-present in `mk/tests.mk` (git-diffed against
  `HEAD:Makefile`). Pitfall caught mid-work: the first extraction truncated the
  `test-agent-skills-live` recipe (2 lines left orphaned in the Makefile,
  `unit_tests.py check` red) — fixed by moving the exact `HEAD:Makefile` lines.
- `make check-wiring` rc=0; `python3 scripts/unit_tests.py check` rc=0 (readers
  already include-aware, no reader change); `make help` output byte-identical
  (help is a static echo target).
- Docs: `docs/ARCHITECTURE.md` `mk/` row now names `tests.mk` citing #2677;
  `docs/changes.d/` fragment + `make changes-index` row.

## Current status

Branch `feat/2677-makefile-tests-mk` off `origin/main`; full `make test-unit` and
the OpenSpec validation run locally; PR drives CI green against `main`. Sibling
order note from #2677: `test-clean`'s home moved here FIRST, so #2675's extraction
of its recipe logic rebases onto this branch, not the reverse.
