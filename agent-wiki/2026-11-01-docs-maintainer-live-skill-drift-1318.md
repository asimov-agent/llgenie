# Documentation-maintainer live skill drift fold (merge-event-is-not-green-proof)

## What changed

The documentation-maintainer lane's live SKILL.md grew **+1,235 b** (73,822 vs 72,587) — a third
consecutive fold this session — accumulating the lesson this morning proved: **a merge event is not
proof its gates went green**. Verify the *head sha's* check-runs directly before ever reporting "CI
green at the merge":
`gh api repos/<r>/commits/<head>/check-runs?per_page=100 --jq '.check_runs[]|{name,status,conclusion}'`
(cross-check the matrix job via `repos/<r>/actions/runs/<id> --jq '{status,conclusion}'`). An
owner/planner gate can merge through a still-`in_progress` deciding leg; `status: in_progress` /
`conclusion: null` means it **never completed** — say "merged through a pending deciding leg" and
correct any teammate premise that called it green. Live is source of truth; the tree catches up
byte-identically (#791).

## Files

- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` — live→tree
  byte-identical fold (73,822 b). `SOUL.md` and `references/docs-freshness.md` unchanged (16,175 /
  4,026 b, already aligned).
- `CHANGES.md` — re-rendered by `make changes-index` (this issue's row).
