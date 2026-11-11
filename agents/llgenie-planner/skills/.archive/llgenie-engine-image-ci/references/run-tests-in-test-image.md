# Every pytest invocation in a recipe runs inside the test image

A make recipe that runs pytest MUST prefix EVERY pytest invocation with the
container runner (`$(TEST_RUN)`), never bare `python3`. The failure class is the
recipe's SECOND call: a target that mounts its first pytest through
`$(TEST_RUN)` and then runs a related test (`python3 tests/test_engine_version.py ...`)
with BARE `python3` silently runs that second invocation on the HOST python,
outside the test image (which holds `gguf`/`numpy`).

## Symptom

A post-build / post-publish gate is red with the same failure for EVERY
engine bump, and the red is not auth or a stalled download. The build job is
green while its post-build test (`test-published-*` / version check) fails
identically across all chore engine-bump PRs on the same class.

## Diagnosis / fix

- Diff the red recipe's pytest lines against its sibling target's
  (`test-engine-image` vs `test-engine`): the sibling mounts every call through
  `$(TEST_RUN)`, the red one has a bare `python3 ... test_engine_version.py` line.
- Mount that second invocation through the SAME `$(TEST_RUN)` the first one uses
  -- a bare `python3` line is the defect, not a subtle test bug.
- Grep the recipe for every `python3`/`pytest` occurrence before trusting a
  "second pytest" step; a container-prefixed first call does not prove the
  others are too.

## Rule

Every pytest call in a current-target recipe runs in the test image, including
the second and any later invocation. A bare interpreter on the host is never
the intended runner.
