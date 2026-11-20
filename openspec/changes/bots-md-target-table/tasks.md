# Tasks: bots-md-target-table

- [x] `scripts/check_docs.py`: add the marker constants, the named-in-prose extractor, the one
      generator `bots_table(root)`, and `bots_table_problem(root)` comparing the block to it
- [x] `scripts/check_docs.py`: `check` mode fails on a missing/stale block (finding names
      `make bots-targets-index`); add modes `bots-table` (print) and `bots-table-write` (rewrite)
- [x] `mk/gates.mk`: host targets `bots-targets-report` and `bots-targets-index` (+ `.PHONY`);
      no `tests/fixtures/host-only-wiring.json` entries — neither target claims CI coverage, and
      that fixture is exactly for claims without jobs (`check-wiring` reddens an entry anyway)
- [x] `scripts/check_architecture_census.py`: strip the generated block before reading BOTS.md
      prose claims (the table's verbatim ## help sentences name removed scripts; the census gate
      reads prose claims only)
- [x] `docs/BOTS.md`: the generated section between the markers, rendered by
      `make bots-targets-index` (130 rows at this head)
- [x] `tests/test_check_docs.py`: pins — table carries the Makefile help text; reworded help text
      reddens `check` naming the render target; render output equals the text the check compares;
      missing block is a finding; the generated block cannot document its own membership
- [x] docs land: `agent-wiki/2026-11-20-bots-md-target-table-681.md` note +
      `docs/changes.d/` fragment + `make changes-index` row
- [x] final proofs, replayable at the committed head: `make -s openspec-validate
      NAME=bots-md-target-table` rc=0; `pytest tests/test_check_docs.py tests/test_architecture_census.py`
      rc=0 (35 passed); `make bots-targets-index && make check-docs` rc=0; `make check-wiring`
      rc=0; `make check-package-layers && make check-import-roots && make lint` rc=0

Ship (not a task): `make lane-preflight`, rebase onto `origin/main`, push
`feat/bots-md-target-table-681`, open the same-repo PR closing #681.
