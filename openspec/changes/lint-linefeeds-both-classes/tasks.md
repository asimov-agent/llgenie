# lint-linefeeds-both-classes

- [x] `scripts/lint_linefeeds.py`: `failed = False` accumulator; the `trailing-newline` block prints and sets `failed` when `bad`; the `markdown-heading` block prints and sets `failed` when `md_bad`; single `if failed: return 1` at the end (the issue's exact suggested form)
- [x] `tests/test_lint_linefeeds.py`: `test_both_classes_are_reported_before_returning` — a fixture with no trailing newline AND a heading-after-content prints BOTH headers and exits 1
- [x] `tests/test_lint_linefeeds.py`: the clean-file case still exits 0 via the aggregate OK
- [x] `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` re-rendered with `make changes-index`
- [x] `make lint`, `make check-docs`, `make check-pr-hygiene` and `make openspec-validate NAME=lint-linefeeds-both-classes` green
