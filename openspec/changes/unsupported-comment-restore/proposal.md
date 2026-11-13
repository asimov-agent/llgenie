# Change: unsupported-comment-restore (issue #2639)

## Why

The `# UNSUPPORTED=<file>` comment block documents the `UNSUPPORTED ?=` variable, which lives in
the top Makefile. The security-domain split (#2459, merged via PR #2637) moved the block: its
extraction span (target line through first blank line OR next target header) ran across the
comment because it sat between the last security target and `UNSUPPORTED ?=` with no blank line
ending the span. The block now sits at the tail of `mk/security.mk` (line 139) while the variable
it documents stays in the top Makefile with no adjacent explanation.

## What Changes

- The `# UNSUPPORTED=<file>` comment block (5 lines) is moved out of `mk/security.mk` and back to
  its position immediately above `UNSUPPORTED ?=` in the top Makefile.
- Comment-only: no target, prerequisite, recipe, `.PHONY` entry or variable assignment changes.
  Parity proven by `make -qp` target list diff empty and `make help` byte-identical vs the parent
  commit, plus `make check-wiring` unchanged.

## Scope boundary

Only the two files above. No reader, test, workflow or skill changes.

## Impact

- Affected specs: `unsupported-comment-restore` (the variable is documented where it is set).
- Affected code: `Makefile`, `mk/security.mk`, docs trio (`docs/changes.d/`, `agent-wiki/`).
