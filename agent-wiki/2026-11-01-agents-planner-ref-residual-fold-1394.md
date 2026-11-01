# agents(planner): fold residual live-longer drift in 4 bot-orchestration references — #1392 accepted on a stale snapshot (#1394)

The #1392 fold (issue #1390) merged at `5c5df3d1` captured a snapshot of the planner profile,
but the live lane kept editing several `llgenie-bot-orchestration/references/*.md` files
after the snapshot (mtimes 15:48–16:06Z) and before/around the merge. `scripts/check_agent_profiles.py`
from a clean worktree at `5c5df3d1` reported residual `live-longer` drift in **four** files
(the three the issue did not enumerate appeared as I re-measured; #1273 requires the whole
`agents/llgenie-planner/skills/` bundle —refs + templates— at ZERO planner lines, so all four
are in scope):

- `references/stalled-lane-and-dispatch-delivery.md` — 28,117 → 35,095 b (the issue's named file)
- `references/merged-over-red-gate.md` — 3,248 → 5,407 b
- `references/completion-integrity-check-handling.md` — 3,447 → 4,826 b
- `references/shell-and-body-safety.md` — 3,799 → 5,214 b
- `references/profile-fold-verification.md` — 4,138 → 6,734 b

Each copied live → tree verbatim, `cmp` byte-identical at the fold head. The live profile was
re-measured for stability (consecutive same-signature reads) before each copy, and re-verified
against live immediately before commit.

**Bundle-wide acceptance (measured at the fold head):** `scripts/check_agent_profiles.py` reports
**ZERO** `llgenie-planner` lines from a clean worktree at the fold head (no live-longer, no
absent-from-tree, #1273). `make check-docs` rc 0 (census gate OK).

`AGENTS:` preflight — base = origin/main `5c5df3d1` (16:04Z fetch; small self-contained repo,
make-target verification, ghost-gate discipline honoured).

