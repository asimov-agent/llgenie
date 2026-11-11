# Tasks — force-phrase-instruction-drift (#2502)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=force-phrase-instruction-drift`)
- [x] 2. Re-measure the surface at `8a4bc26df` and adjudicate every hit (55 hits / 47 files:
  36 corrected, 10 kept-qualified, 9 kept) — recorded in `proposal.md`
- [x] 3. Apply the 36 corrections + explicit qualifications to the `agents/` instruction surface
- [x] 4. Add `tests/test_force_phrase_instruction_surface.py` (discovered by `scripts/unit_tests.py`)
  with the allow-list fixture and the planted stale-tuple fixture that must red
- [x] 5. Verify locally: the hygiene test passes against the live surface (3/3, planted stale
  fixture reported); `make openspec-validate NAME=force-phrase-instruction-drift` exits 0;
  `make test-unit` is green with the new test included in the discovery (`pytest` 3 passed rc=0; `make test-unit` 3619 passed rc=0)
- [x] 6. Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry
  (`make changes-index` rc=0, `make check-docs` rc=0 at `48a061321`)
- [x] 7. Final verification: `python3 scripts/check_pr_acceptance.py check --body-file <PR body>`
  replays rc=0 against the body carrying `closes #2502`, the eight `SYNC:` lines, and
  `#2451`/`#2498` provenance; `make check-tick-prompt` rc=0
