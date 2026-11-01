# agents(planner): fold the planner's two skills live→tree — versioning trail #1370/#1371/#1372/#1373

The planner's live profile skills were ahead of the versioned tree by four trailing lessons
from the 2026-11-01 arc; each was an un-versioned private edit, the exact class #791 forbids.
This PR versions them byte-for-byte live→tree (the #1273 / tree==live standard) in ONE vehicle.

**`agents/llgenie-planner/skills/github-issue-triage/SKILL.md` — CREATED (29,739 b).** The file
was entirely absent from the tree (`git log --all` empty, `git grep 'name: github-issue-triage'`
matches nothing under `agents/`), so the issues' "single-bullet insertion, other bullets
unchanged" acceptance was unsatisfiable as written — whole-file creation IS the fix. It carries:
- **#1370** — the close-audit "Residual / could-be-issued" rule (the #1148 straggler lesson).
- **#1372** — the "pre-existing-gate red / CHECK for a merged covering PR" dispatch-race guard
  (the #1367/#1369 loop).

**`agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` — UPDATED (107,515 → 112,364 b,
+30/−1).** Carries:
- **#1371** — the loop-escape deflection clause (the #1348 three-time-correction loop).
- **#1373** — the parked-initiative / product-manager+business-analyst planning bullets (~66-70)
  and the "Filing the trail issue is half the mutation" + "Validate a live edit is genuinely
  tree-absent" lessons (~328-349).

Both tree copies prove byte-identical to the live profile with `cmp`. Measured at `origin/main`
`b5851814` (15:00Z re-fetch; live files re-read the same moment — bot-orchestration had grown
774 b during intake, which is exactly why the copy is taken at fold time, not at branch-cut).

`AGENTS:` preflight — base = origin/main `b5851814`, read at 14:48Z/15:00Z (git workflow
contract, issue-body six-section order, closes-keyword adjacency all honoured). Change-note pair
ships in this same PR per the #1123 gate.
