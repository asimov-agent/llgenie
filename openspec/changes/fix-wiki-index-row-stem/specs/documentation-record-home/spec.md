## ADDED Requirements

### Requirement: an agent-wiki note's own index row links the stem that exists

Every `agent-wiki/<stem>.md` note that carries a self-referential index row SHALL link a target file
that exists in the tree; a broken internal link in the docs corpus is a finding that routes through the
implementation queue (issue #2947, audit contract #2371).

#### Scenario: the 2026-11-07 check-pr-base note reads clean

- **WHEN** the internal-link scan walks `agent-wiki/**` and `docs/**` at the merged main tip
  (resolve each markdown link repo-root-relative, then file-relative; skip external URLs and
  angle-bracket placeholders)
- **THEN** it reports 0 broken links, and
  `grep -c '](agent-wiki/2026-11-07-check-pr-base-stale-clean-attribution.md)' agent-wiki/2026-11-07-ci-check-pr-base-stale-clean-attribution.md`
  prints 0

#### Scenario: docs gates stay green

- **WHEN** `make check-docs` runs at the merged main tip
- **THEN** it exits 0 with the new fix note carrying its own index row and issue reference
