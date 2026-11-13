# Restoring the `# UNSUPPORTED=<file>` comment above `UNSUPPORTED ?=` (issue #2639)

One misplaced comment block from the security Makefile split (#2459, merged as PR #2637).
This chore (issue #2639, PR #2643, branch `chore/restore-unsupported-comment`) ships its
move back; no target, recipe or variable changes.

## What changed

The security split moved target blocks from the top `Makefile` into `mk/security.mk` using
the family span rule: a block runs from its target line through the first blank line OR the
next target header, whichever comes first, tracking `ifeq` depth. `renovate-report` (the last
security target) has no blank line after its recipe before the `# UNSUPPORTED=<file>: …`
comment cluster and the `UNSUPPORTED ?=` assignment that follow in the top file, so the span
carried the 5 comment lines across the cluster boundary: they ended up at the tail of
`mk/security.mk` (line 139 on `908639c1e`, 142 on `0527eb0ac`) documenting nothing there,
while `UNSUPPORTED ?=` in the top `Makefile` (line 886 on `908639c1e`) lost the explanation
of the trend-store omission rule and issue #229 provenance.

The fix is comment-only: the identical 5-line block re-inserted immediately above
`UNSUPPORTED ?=` in the top `Makefile`, deleted from the tail of `mk/security.mk` (the file
now ends with the `renovate-report` recipe).

## Verification

- `git diff` audit: 5 insertions / 5 deletions, the +/- lines byte-identical.
- `make -qp` target-name extraction (method `grep -oE '^[a-zA-Z0-9_.-]+:'`) diff empty vs
  origin/main `908639c1eae1f0d67b3bf1beae47a8397078062a`: 458/458 (`TARGETS_IDENTICAL`).
- `make help` byte-identical (`cmp` `HELP_IDENTICAL`).
- `make check-wiring` rc=0, `make lint`, `make check-workflows`, `make check-docs`,
  `make lane-preflight` rc=0; hermetic unit battery `make test-unit` rc=0 on the PR head.

## Current status

OpenSpec change `restore-unsupported-comment` fully ticked; issue #2639 closed by this PR's
merge.
