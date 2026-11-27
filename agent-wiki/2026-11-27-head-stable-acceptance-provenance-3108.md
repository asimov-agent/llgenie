# Head-stable acceptance provenance (issue #3108)

Branch `agent/issue-3108-head-stable-provenance`, cut from freshly fetched `origin/main@4b1fcb2bbee47b57d697b96e8737089a00cde952`.

## What changed

- `scripts/check_pr_acceptance.py` now resolves a ticked criterion's `(proven: …)` head with the merge-ancestor rule: exact/abbreviated equality passes, a cited head that is an ancestor of the measured `--rev` also passes, and an unrelated head, a descendant, a missing object or a non-commit token still emits the blocking `tick-stale-head-unflagged` finding.
- Both stale-head paths use the same resolution: the run-cited path (green run head / named heads) and the command+`rc`+`sha` path with no `run=`.
- The live-run evidence rules are unchanged: a tick citing a red or unreadable run still reds; no gate step is skipped or weakened.
- Regression tests build a real tiny git history (base → head plus unrelated sibling) and cover ancestor clean, sibling red, unresolvable red, and ancestor-with-red-run red.

## Why

PR #3105 was red-flagged three times in one session (`5f5c720fa389` → `4577eb998d71` → `ed0fc689b20e`) because the four #3096 ticks were proven at `4577eb99`. The verdict and ticks were real; only the head reference was stale. Re-ticking after every push treated the symptom and recurred. An ancestor proof is evidence measured earlier in the same history; a push that keeps that commit in the PR's ancestry no longer invalidates it.

## Verification

`make openspec-validate NAME=acceptance-provenance-ancestor-3108`, `make -s check-docs`, focused `pytest tests/test_check_pr_acceptance.py -q` (83 passed), and a production-seam check against this worktree's real history all run at the pushed head. Run ids and head sha are recorded on issue #3108 and PR body.

## Not covered

- The grype pin itself (#3096) and its digest — untouched.
- No merge, no arm, no self-tick (#1088/#1644).
