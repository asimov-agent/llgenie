# Tasks: fix-wiki-index-row-stem

- [x] 1. Point the index-row link in `agent-wiki/2026-11-07-ci-check-pr-base-stale-clean-attribution.md`
      at the file's own basename (the stem that exists). — done; grep for the broken stem prints 0.
- [x] 2. Add the fix note trio: `agent-wiki/2026-11-19-fix-wiki-index-row-stem-2947.md` +
      `docs/changes.d/2026-11-19-fix-wiki-index-row-stem-2947.md` + `make changes-index` row. — done;
      CHANGES.md gained its row (+1 insertion).
- [x] 3. Proofs: grep for the broken stem prints 0; the #2371 link-scan recipe over
      `agent-wiki/**` + `docs/**` reports 0 broken links (1846 files scanned, 0 broken);
      `make check-docs` and `make lint` rc=0.
- [x] 4. `make openspec-validate NAME=fix-wiki-index-row-stem` exits 0 — "Change 'fix-wiki-index-row-stem' is valid".
