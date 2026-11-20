# Proposal: bots-md-target-table

## Why

Issue #681. After #678 the automation targets are documented in `docs/BOTS.md` and the user
targets in `README.md`, but the lists are hand-written prose. `make check-docs` only proves that
each `##`-help target is *named* somewhere in the documentation surface — it cannot see that the
description beside the name drifted from the Makefile's own `##` help text, which is what
`make help` prints. A reworded help line (a routine edit) leaves the docs saying something else,
and no gate notices.

## What Changes

- `scripts/check_docs.py` gains ONE generator function `bots_table(root)` that renders the
  per-target table (name + the Makefile's `##` help text) for the make targets named in the
  prose of `docs/BOTS.md`, plus the staleness check `bots_table_problem(root)` that compares the
  generated table against the block between new `<!-- bots-targets:begin -->` …
  `<!-- bots-targets:end -->` markers. The renderer and the validator call the same function —
  no second copy of the rule.
- `make check-docs` (already in `ci-unit`) fails when that block is missing or stale; the failure
  names the regeneration target. No new ci-unit step is added.
- `scripts/check_docs.py` gains two render modes: `bots-table` (print the table) and
  `bots-table-write` (rewrite the block in `docs/BOTS.md` in place). New host targets
  `make bots-targets-report` and `make bots-targets-index` live in `mk/gates.mk`; neither claims
  CI coverage, so neither enters `tests/fixtures/host-only-wiring.json` (that fixture is exactly
  for targets whose help claims CI without a job — the staleness verdict ships through
  `check-docs`, which CI already runs).
- `docs/BOTS.md` gains the generated target-table section between the markers.
- `scripts/check_architecture_census.py` strips the generated block before reading BOTS.md prose
  claims: the table carries whole ## help sentences verbatim (some name long-removed scripts),
  and the census gate reads PROSE claims only — the same strip check_docs applies to its own
  prose scans.

## Out of scope

- Regenerating the README's user-target prose (the README half of #678 stays prose; the generated
  table lives only in `docs/BOTS.md`, the automation surface).
