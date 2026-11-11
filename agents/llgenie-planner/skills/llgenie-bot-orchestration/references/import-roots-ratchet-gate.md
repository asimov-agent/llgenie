# `make check-import-roots` — the ratchet that reds a PR's OWN new test file

Gate: `make check-import-roots` (Makefile:401, issue #796/#1101). It counts import roots
against a recorded baseline at `tests/fixtures/import-roots-baseline.json` and REFUSES an
increase. Failure text is specific and quotable:

```
[import-roots] bare: a NEW import root is refused — this exactly (issue #1101):  (NN now, MM recorded)
  tests/test_<new>.py:<line>
[import-roots] sys-path: a NEW import root is refused — this exactly (issue #1101):  (NN now, MM recorded)
```

## Why it bites a fix PR

A lane fixes a classifier/dispatch defect, adds a NEW test module `tests/test_<thing>.py`, and
that test does `sys.path.insert(0, REPO/"scripts")` + bare `import <script_module>`. That is a
new sys-path root AND new bare roots -> the ratchet reds `linux/unit` on the lane's *own* diff.
Signature: everything else in unit passes (all `# proc-allow:` markers OK), then
`make[1]: *** [Makefile:403: check-import-roots] Error 1` -> `make: *** [Makefile:1801: ci-unit] Error 2`.

## Remedy (prefer the seam)

1. **Preferred:** draft the test to reuse the existing scripts-import seam (`tests/conftest.py`)
   instead of `sys.path.insert` + bare script-module imports - keeps the roots flat.
2. Only if (1) is impossible: re-record the baseline at what the branch legitimately produces
   (`scripts/check_import_roots.py` docstring, `--root <exported tree> report`).

## Orchestrator lesson

When a unit red persists through several lane pushes on a dispatch/classifier fix, check
`make ci-unit`'s step log for `check-import-roots` BEFORE assuming the fix failed - the
proc-gate fix can be green while the lane's new test file is the actual offender. Name the
exact file+lines and the two counts in the dispatch; the lane owns the file (own vehicle, one PR).
Also: SKILL.md is at the 100k ceiling, so new lessons land as reference files (add a pointer
only after trimming another section).
