---
name: fix-import-roots-new-file-spelling
about: New tests must import scripts/ modules as `from scripts import <name>` — a durable docstring note in check-import-roots (issue #2032)
status: active
---

# A new test imports a scripts/ module as `from scripts import <name>` (issue #2032)

## Proposal

The `check-import-roots` ratchet (`make check-import-roots`, issues #796/#1101) records every bare-import
site in `tests/fixtures/import-roots-baseline.json` and **refuses any rise**: a NEW bare `import <name>`
of a `scripts/` module trips "a NEW import root is refused" naming that exact file:line. The risk is that
an author copying a sibling test's top lines copies the **wrong** shape — the siblings' bare imports and
`sys.path.insert` bootstraps are REMAINING refactor debt (recorded so the migration may only shrink,
never rise), not the accepted spelling for a new file.

## Change

Add a durable note to `scripts/check_import_roots.py`'s module docstring, immediately after the `bare`
rule description (lines 11-13): a NEW test file must import a `scripts/` module as
`from scripts import <name>`, never `import <name>`; the recorded bare-import debt may only shrink, never
rise; and copying a sibling's bootstrap copies refactor debt, not the accepted spelling. No ratchet logic,
no baseline edit, no engine/serving change.

## Motivation

A new test author who sees a sibling with a bare import copies it, trips the ratchet, and burns a CI
cycle diagnosing "a NEW import root is refused" — measured live on PR #2025 (run 42388284880, `linux /
unit`): `tests/test_check_main_ruleset.py:14` `import check_main_ruleset as rs` added the 56th bare site
(recorded baseline 55) and the gate went red naming exactly that file:line. The guard's own guidance must
live next to the rule that refuses the wrong spelling, so the correct shape is the obvious one.

## Acceptance

- `scripts/check_import_roots.py`'s docstring states that a NEW bare `import <name>` of a `scripts/`
  module is refused and the correct new-file spelling is `from scripts import <name>` (issue #2032's
  acceptance criterion).
- `python3 scripts/check_import_roots.py ratchet` EXIT=0 at the head (baseline untouched — a doc-only
  change adds zero sites).

## Relation

- **#2032** — the issue this change implements; its single acceptance criterion is the docstring note.
- **#796** — the ratchet's origin (the migration may only shrink).
- **#1101** — the set-shaped baseline (a red names the one new file:line).
