# LLGenie Pipeline Maintainer: a landed/closed-PR head ends the auto-merge run green (#897)

Implements issue #897 (ready-for-review PR, never merged). `auto-merge`'s `resolve` step was
meant to treat a completed CI run whose head already has a MERGED or CLOSED PR as a **non-event**:
the fix in PR #898 made `scripts/resolve_run_pr.py` exit 0 with an empty `number=` output for that
head. But the workflow's **merge step still ran** `make auto-merge PR="$PR"` regardless — its `if:`
only checked the event name / channel, never whether a PR actually resolved — so the guard tripped
with `Usage: make auto-merge PR=<n>` and the run went red. Measured: run 41289340450 (2026-11-01,
`completed/failure`), which logged `nothing to merge: PR #1128 for head andyholst:fix/1111-… is
closed (issue #897)` from the resolver, then died at `Makefile:1001` on the empty PR.

## What changed (measured on this worktree)

- `.github/workflows/auto-merge.yml` — the merge step's `if:` now also requires
  `steps.pr.outputs.number != ''`: a head whose PR MERGED/CLOSED resolves to an empty `number=`
  and must NOT run the merge step (nothing to merge) — the step skips and the job ends green.
  A head that **never had a PR** still fails loudly: the `resolve` step itself exits 1 (no `--allow-none`),
  so the job is red before the merge step's guard is even reached (negative control preserved).
- `tests/test_auto_merge.py` — updated the pin in `test_the_scope_sweep_skips_a_code_head_and_decides_once`
  to assert the new `if:` carries the `steps.pr.outputs.number != ''` guard plus the empty-`number=`
  rationale.

## Verification (measured, not asserted)

- `python3 -m pytest tests/test_auto_merge.py tests/test_resolve_run_pr.py -q`: **78 passed**
  (both the workflow-gate file and the resolver file that carries the stubbed-gh landed-head test).
- `python3 scripts/check_workflows.py check`: exit 0 — the new `if:` expression parses and the
  `workflow_run` roster is still fully routed.
- No change to `REQUIRED_MERGE_STATE`; a red or cancelled check never reaches the merge step (the
  job `if:` still demands `conclusion == 'success'`).
