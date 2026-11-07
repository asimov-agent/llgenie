# check-import-roots docstring states `from scripts import <name>` for new files (#2032)

The `check-import-roots` ratchet (`scripts/check_import_roots.py`, issues #796/#1101) refuses any rise in
the recorded bare-import debt: a NEW bare `import <name>` of a `scripts/` module trips "a NEW import root
is refused" naming that exact file:line (measured on PR #2025, `tests/test_check_main_ruleset.py:14`).
The guard's module docstring now states the accepted spelling for a new file — `from scripts import
<name>`, never `import <name>` — and that the siblings' bare imports and `sys.path.insert` bootstraps are
REMAINING refactor debt the migration may only shrink, never rise. Doc + guidance only: no ratchet logic,
no baseline edit, no engine/serving change. Verified at the head with
`python3 scripts/check_import_roots.py ratchet` EXIT=0 (#2032).
