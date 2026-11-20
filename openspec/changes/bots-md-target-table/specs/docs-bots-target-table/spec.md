# Spec delta: docs-bots-target-table

## ADDED Requirements

### Requirement: The BOTS.md target table is generated from the Makefile's help text
The repository SHALL render, inside `docs/BOTS.md` between `<!-- bots-targets:begin -->` and
`<!-- bots-targets:end -->` markers, one table row per make target named in the prose of
`docs/BOTS.md` that carries a `##` help line — the row pairs the target name with the Makefile's
own `##` help text, obtained through the same target extractor `check-docs` already uses. One
generator function SHALL serve both the render and the staleness check; no second copy of the
rule may exist.

#### Scenario: a reworded help line reddens the gate
- **WHEN** a target's `##` help text changes in a Makefile and `docs/BOTS.md` still carries the
  table generated from the old text
- **THEN** `make check-docs` exits non-zero and names `make bots-targets-index` as the
  regeneration command

#### Scenario: the render is byte-identical to the check
- **WHEN** `make bots-targets-index` writes the generated block
- **THEN** `make check-docs` passes with no further edit, because the check compares against the
  same generated text the render wrote

### Requirement: The render targets are host-side and recorded as such
`make bots-targets-report` (print the table) and `make bots-targets-index` (rewrite the block)
SHALL be host-side render helpers recorded in `tests/fixtures/host-only-wiring.json`; the stale
verdict ships inside `make check-docs`, which `ci-unit` already runs, so no new ci-unit step is
needed.

#### Scenario: the staleness verdict runs in CI without a new step
- **WHEN** `ci-unit` runs `make check-docs` against a checkout whose BOTS.md target table is
  stale
- **THEN** the step fails naming the stale table, and the CI step roster is unchanged
