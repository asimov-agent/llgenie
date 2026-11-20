# BOTS.md target table generated from the Makefile help lines (#681)

## What was built

`docs/BOTS.md` now carries a generated target table between
`<!-- bots-targets:begin -->` / `<!-- bots-targets:end -->` markers: one row per make target
the prose of `docs/BOTS.md` names (`make <name>`) that carries a `##` help line, pairing the
name with the Makefile's own help text — the text `make help` prints. Before this, `check-docs`
only proved each target was *named* somewhere; a reworded help line could leave the docs beside
it quietly stale and no gate noticed (issue #681).

- `scripts/check_docs.py::bots_table(root)` is THE generator: the render and the staleness
  check call the same function, so the checked text is byte-identical to the written text.
- `bots_table_problem()` reddens `make check-docs` (already a ci-unit step — no new CI step)
  when the block is missing or no longer matches the generator; the finding names the fix
  command. `bots_table_write()` rewrites the block in place.
- Membership comes from the prose only: the generated block is stripped before scanning for
  `make <name>` references, so a table can never document its own membership.
- Host targets: `make bots-targets-index` (render) and `make bots-targets-report` (print),
  recorded in `tests/fixtures/host-only-wiring.json`; both live in `mk/gates.mk`.

## Decisions

- The table lives in `docs/BOTS.md` (the automation surface), not in `README.md` — same rule as
  the dispatch table: no generator rewrites the user guide.
- The README's user-target prose stays prose (out of scope, per the issue).
- A checkout without `docs/BOTS.md` at all is not a target-table problem (the docs-surface rule
  already answers that); once the file exists, the block must.

## Status

129 rows rendered from the current Makefiles (130 after naming `bots-targets-report` in prose).
Pins in `tests/test_check_docs.py`: reworded help text reddens `check` naming
`make bots-targets-index`; render-then-check is byte-identical; a missing block is a finding.

Issue: [#681](https://github.com/asimov-agent/llgenie/issues/681)
