# Tasks: bots-md-target-table

- [ ] `scripts/check_docs.py`: add the marker constants, the named-in-prose extractor, the one
      generator `bots_table(root)`, and `bots_table_problem(root)` comparing the block to it
- [ ] `scripts/check_docs.py`: `check` mode fails on a missing/stale block (finding names
      `make bots-targets-index`); add modes `bots-table` (print) and `bots-table-write` (rewrite)
- [ ] `mk/gates.mk`: host targets `bots-targets-report` and `bots-targets-index` (+ `.PHONY`),
      recorded in `tests/fixtures/host-only-wiring.json`
- [ ] `docs/BOTS.md`: the generated section between the markers, rendered by
      `make bots-targets-index`
- [ ] `tests/test_check_docs.py`: pins — table carries the Makefile help text; reworded help text
      reddens `check` naming the render target; render output equals the text the check compares;
      missing block is a finding
- [ ] docs land: `agent-wiki/` note + `docs/changes.d/` fragment + `make changes-index` row
- [ ] final proofs, replayable at the committed head: `make -s openspec-validate
      NAME=bots-md-target-table` rc=0; `pytest tests/test_check_docs.py` rc=0;
      `make bots-targets-index && make check-docs` rc=0; `make check-wiring` rc=0;
      `make lane-preflight` rc=0

Ship (not a task): push `feat/bots-md-target-table-681` after rebasing onto `origin/main`, open
the same-repo PR closing #681.
