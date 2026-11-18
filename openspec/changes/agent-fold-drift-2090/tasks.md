# Tasks: agent-fold-drift-2090

- [x] Re-measure the drift at the current main (`make -s check-agent-profiles` at `6787a657b6`): 5 findings, four in-lane plus the planner (#2084).
- [x] Verify per-lane line-sets before choosing direction: docs live block ⊆ tree references; engine-improver live inline == tree reference (`+0` live-only lines); pr-reviever tree line newer than live.
- [x] Stamp the reconciliation with version bumps: docs `1.0.25`, engine-improver `1.0.1`, pr-review `1.28.1`.
- [x] Record the fold: `agent-wiki/2026-11-17-agent-fold-drift-2090.md` + `docs/changes.d/` row.
- [x] Reconcile the live side after the commit: deliberate `make sync-agent-profile PROFILE=<lane> FORCE=1` for docs/engine-improver/pr-reviever (28/54/64 files copied), remove the issse live shadow; `make -s check-agent-profiles` prints 1 finding — planner only (#2084).
- [x] Decide the vehicle: post the decision on #1079 citing the three shipped acceptance artifacts and close it (closed/completed, comment 6962175038).
- [x] Prove the lane: unit suite green at the head (4017 passed, rc=0); `make -s openspec-validate NAME=agent-fold-drift-2090` exits 0.
