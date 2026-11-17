# 2026-11-17 — ci-verdict/auto-merge supersede collapse (issue #2885)

OpenSpec change: `ci-verdict-superseded-rows-2885`. Branch `feat/ci-verdict-superseded-rows-2885`,
PR opened against upstream main closing issue #2885.

## Verified against the spec

- New `scripts/head_check_rows.py` implements the ADDED requirement in
  `openspec/changes/ci-verdict-superseded-rows-2885/specs/check-row-supersede/spec.md`: for each
  (job name, workflow file) group in a head's check-run rows, only the newest CONCLUDED row (ordered
  by `started_at`/`completed_at`, tie-broken by row id) governs; strictly-older concluded rows are
  superseded and never block. Unconcluded rows neither supersede nor are superseded; rows whose
  workflow file cannot be resolved are never superseded.
- `scripts/ci_verdict.py::unjudged_reds` filters its candidates through the shared collapse and
  prints each cleared row as a `superseded red (not a block)` note instead of blocking on it; the
  judged-roster exclusion, the TRANSIENT exemption, and the pinned
  `UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS` parity are untouched.
- `scripts/auto_merge.py::failing_checks` blocks only on non-superseded reds: `_check_runs` now
  projects `id`/`started_at`, and a new `_workflow_file` mirrors `ci_verdict.workflow_of`
  (Actions-run read cached per run id, `""` when unreadable — conservative: a red is never cleared
  on a failed read).
- Measured defect (PR #2882, head `585b03dd740c121564190f86987f9bac89f4e796`): three `scope` rows
  coexist at one head (two `success` from later runs, one `failure` from the since-cleared run
  44046649110); the verdict replay of the fully-green run 44053645969 posted `failure` naming only
  the dead row, and auto-merge refused the head. `filter=latest` returns all three — separate RUNS
  mint separate check-run ids; only re-runs of the same run id collapse. Cost that day: three forced
  head moves (#2882, #2878, #2884).
- Tests: `tests/test_head_check_rows.py` (8 tests, group semantics, ordering tiebreak, unresolved-file
  conservatism, lazy file-resolution), three new `tests/test_ci_verdict.py` supersede tests, three new
  `tests/test_auto_merge.py` tests (merge-on-superseded, defer-on-newest-red,
  defer-when-newer-row-unfinished). Full module runs locally: 182 passed on the first batch, the two
  initial failures were the note missing the run id — fixed in the same change; re-run green.

## Key decisions

- Collapse is one module shared by BOTH readers (`ci_verdict` and `auto_merge`) — the pinned-parity
  test now inspects both sources for the shared call, so the verdict and the merger can never clear
  different rows.
- A superseded red is always LOGGED (run id + row id), never silently dropped — "collapse NEVER
  erases red".
- Ordering falls back `started_at` → `completed_at` → row id, and rows without a usable id are never
  added to the superseded set.

## Current status

Implemented on the branch; gates (`check-package-layers`, unit battery, openspec validate,
lane-preflight) run in the PR batch.
