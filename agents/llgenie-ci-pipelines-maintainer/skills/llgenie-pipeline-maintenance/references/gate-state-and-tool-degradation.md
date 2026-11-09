# Gate-state and tool-degradation lessons (2026-11-08, t_6c74330a)

## A bot PR's `check-pr-acceptance` red is awaiting-review, not a fix failure

`check-pr-acceptance` is review-verdict-gated (#1644/#2187): it reads the LIVE linked issue and reds while an
implementing PR is un-reviewed because the issue's `## Acceptance criteria` boxes are unticked. This is the
normal BLOCKED state for every ready-for-review bot PR (same as #2298/#2304) — NOT a defect of the fix.

The reds the IMPLEMENTER must clear before the PR is reviewable:
- `check-pr-closing`: adjacent `closes #N` must appear in the squash commit message AND the PR body (a bare
  `Issue: #N` line is a claim, not a close).
- `check-pr-agents-line`: the PR body must carry the `AGENTS:`+`BASE:` pair — run
  `scripts/bot_preflight.py --body-file <body> --out <tmp>` to stamp it authoritatively.
- `check-pr-openspec-change`: a product-code change must add an `openspec/changes/<name>/` dir (proposal.md,
  tasks.md, specs/.../spec.md with `## MODIFIED Requirements` + `#### Scenario:` blocks) or name an existing
  one with `OPENSPEC: <name>` in the body.
- `check-pr-base`, `check-pr-closing` squash, `check-pr-hygiene`: also live-read the body; a body-only fix
  clears on rerun.

When the only red is `check-pr-acceptance`, the PR is READY FOR REVIEW: report it, comment the run-id proof
on the issue, and hand the acceptance tick to the reviewer lane. Never self-tick acceptance boxes on your own
issue (verdict-gated by design) and never weaken the gate.

## Post tool-output-degradation verification

When terminal/gh output goes empty (a recurring host degradation across attempts 1-3), WRITES still land but
READS return nothing — so an idempotent mutation (an issue comment) may have run more than once or be
ambiguous. Before finishing: verify what actually landed on the remote (`gh api repos/<r>/issues/N/comments
--jq '.[].id'`) and DELETE any duplicate you caused (`gh api -X DELETE .../issues/comments/<id>`), then
complete. Bookend the worktree: leave the atomic commits on their PR branches, never merge, record the
delivered shas + run ids in the task handoff; never push blind while reads are empty (stand rule 28).
