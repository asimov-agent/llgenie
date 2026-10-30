# architecture-census-gate

- write `scripts/check_architecture_census.py` (check/report)
- add `check-architecture-census` Makefile target, `.PHONY`, wire into `check-docs`
- update `docs/ARCHITECTURE.md` census to current tree + `measured at <sha>` + gate row
- add `agent-wiki` note and `docs/changes.d/` fragment; re-render `CHANGES.md`
- open PR closing #896
