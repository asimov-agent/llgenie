# fix-import-roots-new-file-spelling

## ADDED Requirements

### Requirement: docstring-states-from-scripts-import

`scripts/check_import_roots.py`'s module docstring (the `bare` rule description, lines 11-13) SHALL state
that a NEW test file imports a `scripts/` module as `from scripts import <name>`, never `import <name>`,
and that the recorded bare-import debt may only shrink, never rise (issues #796, #1101).

#### Scenario: the docstring states the accepted new-file spelling

- **Given** `scripts/check_import_roots.py`'s module docstring
- **When** a test author reads the `bare` rule description to learn how a NEW file imports a `scripts/` module
- **Then** the docstring states the accepted spelling is `from scripts import <name>`; a NEW bare `import <name>` of a `scripts/` module is refused by the ratchet; and the recorded bare-import debt may only fall, never rise
- **Test:** `python3 scripts/check_import_roots.py ratchet` exits 0 at the head (a doc-only change adds zero sites; the docstring change itself is asserted by the issue #2032 acceptance criterion)
