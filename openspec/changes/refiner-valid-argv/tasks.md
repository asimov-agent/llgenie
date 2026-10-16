# Tasks

- [x] 1. File the issue with measured evidence (issue #314): the `--comments --json` crash in `make issue-refiner-pick` and in run 38818619593, and the swallowed green no-op.
- [x] 2. Fix `_thread()` to drop `--comments` and keep the `comments` JSON field.
- [x] 3. Make `issue-refiner.yml`'s pick step fail loudly when the pick exits non-zero.
- [x] 4. Add the tests (no `--comments`+`--json`; the step fails loudly).
- [x] 5. Prove the tests fail on the pre-fix tree and pass after (rule 6c).
- [x] 6. Add an `agent-wiki/` entry citing #314.
- [x] 7. Verified: `make lint`, `make openspec-validate NAME=refiner-valid-argv`, `make check-wiring`, `make check-docs`, `tests/test_issue_refiner.py` green in the test image.
