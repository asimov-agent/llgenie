# Makefile split guard: duplicate-target detector + line budget (issue #2674)

## Why

The #800 include-split landed (six `mk/*.mk` files via #2456–#2461), but the two guard
halves #800 itself demanded are missing. Measured at `origin/main@425832c26` (2026-11-15):

- No detector exists for a target name declared twice across the includes. GNU make makes
  that silent: one recipe wins, the other is quietly dropped — the "conflicted Makefile
  mid-run" failure class (#460) #800 cites as its motivation. The tree carries zero
  duplicates today (`grep -hE '^[A-Za-z0-9_][A-Za-z0-9_.-]*:' Makefile mk/*.mk | cut -d: -f1 | sort | uniq -d` → empty), which means nothing prevents the next PR from introducing one.
- No line budget is stated or enforced anywhere (`grep -rin budget scripts/ tests/ docs/ Makefile mk/` → no `mk/` hit). `mk/engines.mk` is already 499 lines; a split without a ceiling re-merges itself back toward the 1,653-line monolith #800 filed to remove.

## What Changes

- `scripts/check_wiring.py` (already include-aware, its `_makefile_list` resolves
  `include mk/*.mk` in file order, citing #800/#2457):
  - **duplicate detector** — collect declared target names per file in include order over
    `Makefile` + `mk/*.mk`; a name declared in two files is a finding naming BOTH files.
  - **line budget** — one committed source of truth,
    `tests/fixtures/makefile-line-budgets.json`: each `mk/*.mk` ceiling 600 lines
    (measured max today 499 — green at landing); top `Makefile` ceiling 977 ratchets
    (recorded at the landing measurement, may decrease, never increases without a dated
    decision entry in that file — the repo's exemption-with-reason pattern).
  - a missing/invalid budget file is itself a finding: the enforcement cannot be silently
    deleted.
- `tests/test_wiring.py` gains controls in each direction: planted duplicate → red naming
  both files; planted over-budget file → red naming file + ceiling; budget file removed →
  red; the budget numbers are DERIVED by the tests from the committed source, never baked
  into test bodies.
- No new wiring: `check-wiring` already runs in `ci-unit`
  (`tests/test_wiring.py::test_the_guard_runs_in_ci_unit_and_this_file_runs_in_test_unit`
  pins it).

## Out of scope

Residual Makefile target extractions themselves (#2675–#2678) — they land under this
ceiling; this change ships only the guard halves #800 criteria 3+4 demand.
