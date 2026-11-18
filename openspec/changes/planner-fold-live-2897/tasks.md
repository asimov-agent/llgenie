# Tasks: planner live-side fold (#2897)

- [x] Measure the lane before any write: line-set diff live vs tree whole lane store — +52 live-only / -0 tree-only; 39/39 live-only content lines verbatim in `references/filters-and-classifiers.md` (8,071 b, linked at SKILL.md:545, :614); live 102,764 b over cap, tree 95,033 b under cap; recorded in `agent-wiki/2026-11-17-planner-fold-live-2897.md`.
- [x] Land the tree shape live: `make -s sync-agent-profile PROFILE=llgenie-planner FORCE=1` rc=0; post-sync gate names no planner finding.
- [x] Version-stamp: planner `SKILL.md` `version: 1.0.0 -> 1.0.1` with the agent-wiki note + `docs/changes.d/` row in the same commit; `make -s check-docs` rc=0.
- [x] Prove fleet-wide zero: `make -s check-agent-profiles` prints 0 findings at the lane head (first time; the 2026-11-08 baseline was 586). This gate proof is the landing evidence ticked onto #2090's fleet-wide-zero AC when the lane lands; #2090 is closed from landing watch, not by this PR.
- [x] Prove the lane: unit suite green at the head; `make -s openspec-validate NAME=planner-fold-live-2897` exits 0.
- [x] After #2896 merges: correct its landed `spec.md` knob wording `--force` -> `FORCE=1` (the knob `mk/agents.mk` implements), in this lane's tree.
