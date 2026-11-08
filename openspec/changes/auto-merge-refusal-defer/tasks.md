# Tasks — auto-merge-refusal-defer (issue #2236)

- [x] 1. OpenSpec change: `proposal.md`, `specs/true-merge-good/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `_merge()` wraps `merge()` in `try/except SystemExit`; on refusal re-reads the PR — already `MERGED` → verify the closure and return success, still `OPEN` → `defer()` with the refusal reason on the PR, exit 0
- [x] 3. `docs/BOTS.md`: two decision-table rows document the already-`MERGED` success and still-`OPEN` deferral outcomes
- [x] 4. `tests/test_auto_merge.py`: 3 new tests (fake-`gh` merge refusal + `merged_after_merge_refusal`) pin `_merge()` behaviour, incl. the negative control that a still-open refusal defers and is never swallowed
- [x] 5. Verified: the 3 new tests fail on the old tree (run `42469582901`-style `SystemExit` propagates) and pass on the new; `make test-auto-merge` → 95 passed; `make check-docs`, `check-import-roots`, `check-package-layers` clean; both outcomes reproduced through `make auto-merge` with a fake `gh` on `PATH`
- [x] 6. PR opened against `asimov-agent/llgenie:main` closing #2236
