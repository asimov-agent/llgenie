# fix-import-roots-new-file-spelling

- [x] `scripts/check_import_roots.py` docstring (bare-rule lines 11-13): a NEW test imports a `scripts/` module as `from scripts import <name>`, never `import <name>`; the recorded bare-import debt may only shrink, never rise; copying a sibling's bootstrap copies refactor debt. Proven with `python3 scripts/check_import_roots.py ratchet` EXIT=0 at the head (baseline untouched).
- [x] `make check-import-roots`, `make lint`, `make check-docs`, `make check-wiring`, `make check-pr-hygiene`, `make openspec-tasks-check`, `make openspec-validate NAME=fix-import-roots-new-file-spelling` green at the head.
