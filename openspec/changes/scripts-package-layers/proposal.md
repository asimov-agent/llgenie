# scripts-package-layers — proposal

Issue: [#795](https://github.com/asimov-agent/llgenie/issues/795)

## Why

`docs/ARCHITECTURE.md` §Scripts presents `scripts/` as five groups — Product path, Security
pipeline, Structural gates, CI entrypoints, Bots and automation — and the tree holds 151 modules in
one flat package. The grouping exists only as a table in the document, so no import and no gate can
answer "is this module allowed to import that one", and a reviewer of a long change cannot tell
whether a new edge crosses a border. The design is real; it is just unwritten.

The one place it was already broken is a genuine cycle: `scripts/engine_bump.py` imports
`engine_params_derive`, and `engine_params_derive` imports `engine_bump` back — inside a function,
which is the tell that the layering was already fighting the code. Nothing fails, the dependency is
invisible to any analysis, and `import scripts.engine_bump` drags in half of the derive pipeline.

## What Changes

- **The layering becomes data.** `scripts/package-layers.json` places every module of `scripts/` in
  exactly one of the five groups and lists every cross-group import the repository has agreed to,
  each with a one-line reason (45 edges, re-measured at `origin/main@ea8c239e`).
- **The layering becomes a gate.** `scripts/check_package_layers.py`, wired as
  `make check-package-layers` inside `make ci-unit`, refuses: a cycle (always, whichever groups it
  spans), a cross-group import absent from the file, an allowlisted edge the tree no longer has (so
  the file cannot rot into fiction), a module no group places, a placement the tree lost, a module in
  two groups, a reason-free allowlist entry, and a group name the doc's §Scripts table does not
  state. Unreadable data is exit 2, never a pass.
- **The cycle is broken the honest way.** The release-archive step both directions need
  (`_release_assets`, `_native_archives`, `_pip_install`, `release_archive_install`, plus the private
  HTTP/token helpers) moves out of `engine_bump.py` into the new
  `scripts/engine_release_archive.py`, which sits below both. `engine_bump` re-exports the moved
  names, so its surface — and the tests that read them from it — is unchanged;
  `engine_params_derive` imports the new module instead of `engine_bump`.
- **The document states the seam.** §Scripts gains the data file, the target and the broken cycle
  beside the group table, and the two new modules get their table rows.

## Not covered

- Moving the modules into real subpackages (`scripts/product/…`, `scripts/bots/…`) — a much larger
  change that rewrites every import site, every `python3 scripts/<x>.py` in the Makefile and the
  generated params. It is only reviewable once this border set is agreed; it stays its own issue.
- The duplicate import roots that make such a move dangerous today: that is #796.
- Growing the allowlist by policing *why* an edge exists beyond its stated reason: the gate records
  the decision, a reviewer argues with it.

Refs: #795 (this issue), #796 (import roots), #830 (the release-archive step being moved),
#2015/#2022 (the §Scripts census gate this complements, not replaces).
