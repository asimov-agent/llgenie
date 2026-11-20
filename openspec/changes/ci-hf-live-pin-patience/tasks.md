# Tasks: ci-hf-live-pin-patience (issue #2973)

## 1. Measure the race on main

- [x] 1.1 Name the red runs and their failing test (44739963771, 44743185352 cascade,
      44749136442-class; `test_every_committed_engine_cell_tag_is_published_live`),
      with the same battery's pins sweep reddening on refs that resolve minutes later
      with zero code change (the measured refs + timestamps live in issue #2973).

## 2. The bounded patience window

- [x] 2.1 `scripts/check_engine_pins_published.py`: one probe sweep per check;
      unresolved refs re-probed every 120 s until ONE bounded deadline
      (`patience_seconds`), green the moment a manifest resolves, loud
      `[pins] PATIENCE ...` lines, the deadline never exceeded.
- [x] 2.2 The window is read only from `ENGINE_PINS_PATIENCE_SECONDS` when no explicit
      value is passed; unset means 0 (PR-lane strictness intact); a non-numeric value
      prints a WARN to stderr and stays 0.

## 3. Wire it into ci-hf-live only

- [x] 3.1 `.github/workflows/ci-hf-live.yml`: the battery step carries
      `ENGINE_PINS_PATIENCE_SECONDS: "3600"`; job `timeout-minutes` 105 ≥ window +
      battery headroom.

## 4. Prove the negative control stays red

- [x] 4.1 Hermetic fixtures: mid-window publication resolves green; a never-published
      ref reds AT the deadline (bounded virtual clock, bounded probe calls); the no-knob
      path probes once per cell and never sleeps; a malformed knob is loud and impatient.
- [x] 4.2 `tests/test_ci_hf_live_workflow.py` pins the env wiring and the timeout
      headroom on the workflow file itself.

## 5. Gates on this tree before push

- [x] 5.1 `make -s check-workflows` rc=0 and `make -s check-wiring` rc=0 on this tree.
- [x] 5.2 The full hermetic unit battery `make test-unit` rc=0 on this tree.
- [x] 5.3 `make -s check-docs` rc=0 (wiki entry + changes.d fragment + CHANGES.md row
      name issue #2973).
