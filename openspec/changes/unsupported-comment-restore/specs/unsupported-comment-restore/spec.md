# unsupported-comment-restore

## ADDED Requirements

### Requirement: the `UNSUPPORTED ?=` variable is documented where it is defined

The `# UNSUPPORTED=<file>` comment block (the trend-store omission rule, issue #229) MUST sit
immediately above the `UNSUPPORTED ?=` variable in the top Makefile, and MUST NOT sit in
`mk/security.mk` (a file that ends with security content). The move is comment-only.

WHEN the top Makefile is read at its `UNSUPPORTED ?=` definition point,
THEN the `# UNSUPPORTED=<file>` comment block appears immediately above it, and `mk/security.mk`
carries no line of that block.

#### Scenario: the comment block is above the variable in the top Makefile

- **Given** the current `Makefile`,
- **When** the line `UNSUPPORTED ?=` is located,
- **Then** the 5-line `# UNSUPPORTED=<file>` block appears immediately above it.

#### Scenario: the security file ends with security content

- **Given** the current `mk/security.mk`,
- **When** it is searched for `UNSUPPORTED`,
- **Then** no line matches (the block no longer strays into the security file).

### Requirement: the move is comment-only and parity-preserving

A comment-only change MUST keep the make surface byte-identical: the `make -qp` target list diff
is empty and `make help` is byte-identical vs the parent commit, rc=0.

WHEN `make -qp` and `make help` run on the changed tree,
THEN the target list matches the parent commit exactly and `make help` output is byte-identical.

#### Scenario: parity gates are unchanged

- **Given** the changed tree containing only the comment move,
- **When** `make -qp` and `make help` run,
- **Then** the target list is identical to the parent commit (diff empty) and `make help` is
  byte-identical, rc=0.
