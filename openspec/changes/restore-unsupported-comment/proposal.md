# Change: restore-unsupported-comment (issue #2639)

## Why

The security split (#2459, PR #2637) moved target blocks out of the top Makefile into
`mk/security.mk`; its extraction span (target line through the first blank line OR the next
target header) ran across the `# UNSUPPORTED=<file>` comment cluster that sat between the last
security target (`renovate-report`) and the `UNSUPPORTED ?=` assignment with no blank line
ending the span. The comment now documents nothing where it lives (tail of `mk/security.mk`)
while `UNSUPPORTED ?=` in the top Makefile has no documentation beside it. The issue measured
this on `0527eb0ac`; re-measured on the current tip `908639c1e` the drift persists
(`mk/security.mk:139`, top `Makefile:886`).

## What Changes

- Move the 5-line `# UNSUPPORTED=<file>` comment block from the tail of `mk/security.mk`
  back to its documented position immediately above `UNSUPPORTED ?=` in the top Makefile.
- Comment-only change: no target block, recipe, or variable moves. Parity is proven by an
  empty `make -qp` target-list diff and byte-identical `make help` against the parent commit;
  `make check-wiring` unchanged.

## Out of scope

- Nothing deferred. Span-rule hardening (a guard that refuses to move comment clusters
  without their adjacent variable) is judged unnecessary here: the rule is already documented
  in the split family, and this issue ships only the misplaced block's move.
