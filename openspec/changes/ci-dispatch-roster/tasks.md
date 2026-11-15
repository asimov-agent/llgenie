# Tasks

- [x] Create the `ci-dispatch-roster` OpenSpec change and write proposal + spec delta
- [x] Rewrite the `AGENTS.md` CI-discipline bullet to name the dispatch roster (owner, a collaborator, GitHub itself) and keep the queue-pumping ban
- [x] Re-pin `AGENTS_PIN_PHRASES` in `scripts/check_ci_discipline.py` to the roster wording plus the queue-pumping ban (blanket-ban phrase removed)
- [x] Add/extend the `tests/test_ci_discipline.py` coverage for the re-pinned phrases (existing section-pin test + real-tree green proof)
- [x] Document the change: `agent-wiki/` dated note + `CHANGES.md` index row
- [x] `make check-ci-discipline` green (`check-ci-discipline: OK`, rc 0)
- [x] `make check-workflows` green
- [x] `make test-unit` green
- [x] `make openspec-validate NAME=ci-dispatch-roster` green
- [x] Write `pr-body.md` with the four labelled parts
