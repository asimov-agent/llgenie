# Tasks

- [x] 1. `agents/llgenie-planner/SOUL.md` cadence sentence replaced with configured-30m + delivered-40.0-min measured truth and its cause. Verified: PR #2447 diff at head d05a9aee (the SOUL.md hunk) — LINT OK at this head
- [x] 2. `orchestrator-tick-contract.md` Schedule line and pitfalls line carry configured-vs-delivered with the completion-re-arm root cause and the #2340 pointer. Verified: same PR diff (both hunks)
- [x] 3. `when-to-use-and-pass-shape.md` hedge "30–45 min" replaced with the measured pair. Verified: same PR diff
- [x] 4. Change notes present (agent-wiki entry + docs/changes.d index row naming #2126 and PR #2447). Verified: files present on the branch; `make lint` OK at this head
- [x] 5. Tick prompt STEP 1 carries the explicit preflight fetch commands ahead of the precedence steps; STEP 3 reports a dirty primary checkout with its blocking paths and forbids cleaning it. Verified: prompt hunks on this branch at the push head
- [x] 6. `orchestrator-tick-contract.md` ordered-pass table carries PREFLIGHT FETCH as step 0, ahead of the precedence step. Verified: table hunk on this branch at the push head
