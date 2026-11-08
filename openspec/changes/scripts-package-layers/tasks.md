# scripts-package-layers — tasks

- [ ] 1. `scripts/package-layers.json` places every module of `scripts/` in one of the five §Scripts groups and lists every cross-group import with a one-line reason
- [ ] 2. `scripts/check_package_layers.py` refuses a cycle, an unstated cross-group import, a stale allowlist entry, an unplaced/lost/duplicated module, and exits 2 on unreadable data
- [ ] 3. `make check-package-layers` exists with a `##` help line, is declared `.PHONY`, runs from `make ci-unit`, and is classified in `scripts/issue_bot_gates.py`'s `DEFERRED` roster
- [ ] 4. `scripts/engine_release_archive.py` owns the release-archive step; `engine_bump` re-exports it and `engine_params_derive` imports it instead of `engine_bump`, so the cycle is gone
- [ ] 5. `tests/test_package_layers.py` proves each refusal on a temp copy of the tree plus the import direction and the doc seam
- [ ] 6. `docs/ARCHITECTURE.md` §Scripts names `scripts/package-layers.json` and `make check-package-layers`, and rows both new modules
- [ ] 7. `agent-wiki/2026-11-08-scripts-package-layers-795.md` + its `docs/changes.d/` fragment are added and `make changes-index` re-renders `CHANGES.md`
- [ ] 8. Verification at the head of this branch: `make check-package-layers`, `make check-wiring`, `make check-docs`, `make check-proc-gate`, `make check-architecture-census`, `make issue-bot-gates-check`, `make lint`, `make openspec-validate NAME=scripts-package-layers` and the `tests/test_package_layers.py` + `tests/test_engine_bump.py` sets under `make test-unit` are all green
