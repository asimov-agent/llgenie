# Tasks: test-agent-profiles-rule-scope

- [x] 1. Reproduce the false red on the pre-fix tree with a lane-named tmp base
      (`TMPDIR=~/.hermes/cache/scratch/llgenie-issse-implementer-base`, module node
      `duplicate_canonical` → FAILED at the substring assertion).
      (proven: rc=1 pre-fix run, 1 failed at tests/test_agent_profiles.py:2685)
- [x] 2. Scope the leak assertion to rule-holder lines: parse the
      `  <name>: <title> stated more than once` entries of the synthetic report and assert
      `not (deduped & names)` instead of `lane not in dup_report`.
      (proven: rc=0 post-fix module run on the same hostile base, 150 passed)
- [x] 3. Add the re-flag control: a synthetic profile named exactly `llgenie-tester` stating the
      canonical block twice must be NAMED as a rule holder by `guard.report` (AC-2 proof inside
      the test).
      (proven: rc=0 — control asserts `llgenie-tester in reflag_names`, green = named)
- [x] 4. Prove both bases: module green with the lane-named `TMPDIR` AND with
      `TMPDIR=/tmp/ptest-clean`.
      (proven: rc=0 both runs, 150 passed each)
- [x] 5. Full unit gate: `make test-unit` rc=0 on this branch.
      (proven: rc=0 — 3887 passed, 13203 deselected in 1206.80s, UNIT_RC=0)
- [x] 6. `make lane-preflight` rc=0; commit (typed, `closes #2330` trailer), push
      `feat/2330-agent-profiles-rule-scope`, PR against upstream main ending `closes #2330`.
      (proven: lane-preflight rc=0 on this tree; branch pushed to origin and PR opened ending `closes #2330`)
- [x] 7. Verification proof on the final tree: module green on both tmp bases; `make
      openspec-validate` rc=0; full `make test-unit` rc=0.
      (proven: openspec-validate rc=0, test-unit rc=0 (3887 passed), module 150 passed on both bases)
