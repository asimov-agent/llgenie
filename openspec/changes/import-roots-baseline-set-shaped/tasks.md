# import-roots-baseline-set-shaped

- [x] `scripts/check_import_roots.py`: ratchet compares per-rule site **sets** — `new` sites (present now, recorded then) are the one-line refusals, `removed` sites (recorded then, gone now) the reported shrink. Baseline is `{rule: {count, sites}}`; `--update` writes it; legacy count-shaped baseline entries still ratchet and carry a once-migrate note.
- [x] `tests/test_import_roots.py`: a planted root reds naming exactly that file:line; a removed root is green and reports the site; a clean tree is green; a legacy count baseline still ratchets. Positive + negative controls pasted.
- [x] `tests/fixtures/import-roots-baseline.json` regenerated set-shaped (`make check-import-roots` green on main tree).
- [x] `agent-wiki/` note + `docs/changes.d/` fragment, `CHANGES.md` re-rendered with `make changes-index`.
- [x] `make check-import-roots`, `make lint`, `make check-docs`, `make check-wiring`, `make check-pr-hygiene`, `make openspec-tasks-check`, `make test-unit` and `make openspec-validate NAME=import-roots-baseline-set-shaped` green.
