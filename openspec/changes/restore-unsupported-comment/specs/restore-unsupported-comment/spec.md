# Restored documentation for `UNSUPPORTED ?=`

## ADDED Requirements

### Requirement: `UNSUPPORTED ?=` is documented at its definition site in the top Makefile

The top `Makefile` carries the 5-line `# UNSUPPORTED=<file>` comment block (trend-store
omission rule, issue #229 provenance) immediately above the `UNSUPPORTED ?=` assignment, and
`mk/security.mk` contains no `UNSUPPORTED` comment block — the file ends with the
`renovate-report` target recipe.

#### Scenario: the comment sits where the variable is set

Given the top `Makefile` on the change branch,
when the 10 lines preceding `UNSUPPORTED ?=` are read,
then they carry the `# UNSUPPORTED=<file>:` comment block with no blank line between the
block and the assignment, and `grep -n UNSUPPORTED mk/security.mk` prints no comment hit.

#### Scenario: the move is comment-only and parity-preserving

Given the parent (pre-change) tree and the change branch,
when `make -qp` target lists are diffed and `make help` outputs compared,
then the target-name diff is empty and `make help` is byte-identical, and
`make check-wiring` reports unchanged wiring (rc=0).
