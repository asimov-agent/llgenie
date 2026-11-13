# 2026-11-13 — Restore the UNSUPPORTED comment block above its variable (issue #2639)

Restores the `# UNSUPPORTED=<file>` comment block to its position immediately above
`UNSUPPORTED ?=` in the top Makefile. The security-domain split (#2459, merged via PR #2637)
swallowed the block: its extraction span (target line through first blank line OR next target
header) ran across the comment because it sat between the last security target and
`UNSUPPORTED ?=` with no blank line ending the span, so the block landed at the tail of
`mk/security.mk` (line 139) while the variable it documents stayed in the top Makefile with no
adjacent explanation.

Verified against the spec (`openspec/changes/unsupported-comment-restore`):

- Top Makefile now carries the block immediately above `UNSUPPORTED ?=`; `mk/security.mk` no
  longer carries any `UNSUPPORTED` line.
- Comment-only parity: `make -qp` target list identical (556 names, diff empty) and `make help`
  byte-identical vs the parent commit `0527eb0ac`, rc=0 on both; `make check-wiring` unchanged.
- `make lint`, `make check-workflows`, `make check-dispatch-forms` untouched (no target, recipe
  or variable change).

Note: `make openspec-validate` and the full containerized loop could not run on this host — the
OpenSpec CLI runs inside `llgenie/openspec:latest` and no container runtime (docker/nerdctl) was
up here. The change directory is written to the CLI's shape; CI runs the validate gate.

Current status: comment move applied and parity-proven against the parent commit; change directory
and docs written; openspec-validate + loop to be confirmed by CI.
