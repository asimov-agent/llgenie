# Tasks — force-phrase-instruction-drift (#2502)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=force-phrase-instruction-drift`)
- [x] 2. Re-measure the surface at `8a4bc26df` and adjudicate every hit (55 hits / 47 files:
  36 corrected, 10 kept-qualified, 9 kept) — recorded in `proposal.md`
- [x] 3. Apply the 36 corrections + explicit qualifications to the `agents/` instruction surface
- [x] 4. Add `tests/test_force_phrase_instruction_surface.py` (discovered by `scripts/unit_tests.py`)
  with the allow-list fixture and the planted stale-tuple fixture that must red
- [ ] 5. Verify locally: the hygiene test passes against the live surface; the planted fixture is
  reported; `make openspec-validate NAME=force-phrase-instruction-drift` exits 0; `make test-unit`
  is green with the new test; `make lane-preflight` prints `preflight: OK`
- [ ] 6. Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry
- [ ] 7. Push the branch, open the PR against upstream `main` carrying `closes #2502`, the eight
  `SYNC:` lines, and `#2451`/`#2498` provenance; tick #2502's acceptance criteria with proven
  evidence so the acceptance gate can pass
- [ ] 8. Final verification: the PR's CI runs are green at the final head and the PR is mergeable
  (mergeStateStatus CLEAN) with the closing reference intact — re-poll the board until armed
