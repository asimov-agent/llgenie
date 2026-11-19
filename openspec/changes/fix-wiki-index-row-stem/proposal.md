# Proposal: fix-wiki-index-row-stem

## Why

Issue #2947 (filed by the 2026-11-19 documentation-lane audit recorded at #2371): the agent-wiki note
`agent-wiki/2026-11-07-ci-check-pr-base-stale-clean-attribution.md` carries an index row (line 1) whose
link target is `agent-wiki/2026-11-07-check-pr-base-stale-clean-attribution.md` — a file that does not
exist; the `ci-` prefix is missing from the stem. `make check-docs` gates CHANGES.md rows but not the
self-referential row inside an agent-wiki note, so it rots silently (measured at origin/main
`cbead8b698`: link scan of 1844 md files under `agent-wiki/` + `docs/` → exactly 1 broken internal link).

## What Changes

- Point the note's own index row at the file's actual basename (one-line content fix in one agent-wiki file).
- Record the fix with its change-note trio (agent-wiki entry + docs/changes.d fragment + CHANGES.md row
  via `make changes-index`), like any merged behaviour change.
- No gate, script, or workflow changes: the finding is a data fix inside the docs corpus.

## Impact

- Affected specs: `documentation-record-home` (new requirement: a note's own index row links the stem that exists)
- Affected code: `agent-wiki/2026-11-07-ci-check-pr-base-stale-clean-attribution.md` (1 line),
  `agent-wiki/2026-11-19-fix-wiki-index-row-stem-2947.md` (new), `docs/changes.d/2026-11-19-fix-wiki-index-row-stem-2947.md` (new), `CHANGES.md` (regenerated row)
- Issue: #2947 (finding), audit pass #2371, contract #1645
