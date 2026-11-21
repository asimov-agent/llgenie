# Tasks: engine-alias-select-2987 (issue #2987)

## 1. Measure the lag on main

- [x] 1.1 Name the lagging cells with their digests at tip `a4afb185e`:
      `edge0:cuda` serves `4a7964de-16ec5d83-cuda` vs committed `4a7964de-874f7c96-cuda`;
      `vllm:cuda` serves `0c57b419-4d7140a3-cuda` vs committed `3a4d82f5-4c1f3eee-cuda`;
      `vllm:rocm` serves `0c57b419-a7edd5e8-rocm` vs committed `3a4d82f5-d04739cb-rocm`;
      26/29 aligned, `ALL=1` rc=0 while liveness ran green on the same tip.

## 2. The alias digest comparison in the gate

- [x] 2.1 `scripts/check_engine_pins_published.py::_probe` gains `alias_check`: for
      each resolved cell probe `<name>:<variant>`; aligned prints `[pins] ALIAS OK`,
      digest-mismatch or absent prints `[pins] ALIAS LAG` naming both digests and the
      `[select] <engine> <variant> <tag-suffix>` contract line; any lag reds.
- [x] 2.2 `check_committed` reads `ENGINE_PINS_ALIAS` when no explicit value is
      passed: `1`/`true` on, unset/`0`/`false` off, malformed WARNs on stderr and
      stays off; knob off the check probes once per cell and the verdict is unchanged.

## 3. Wire it into registry-liveness only

- [x] 3.1 `.github/workflows/registry-liveness.yml`: `ENGINE_PINS_ALIAS: "1"` on the
      fleet gate step and the dispatch-gate step; nothing else in the dispatch path
      changes (it already turns `[select]` lines into `engine-build.yml push=true`).

## 4. Tests in place

- [x] 4.1 `tests/test_check_engine_pins_published.py`: hermetic cases — aligned green
      with `ALIAS OK`; digest lag red with `ALIAS LAG` + `[select]`; absent alias red
      with `[select]`; knob unset → exactly one probe per cell, lag invisible; knob on
      via env; malformed knob loud and off.
- [x] 4.2 Workflow wiring test: both `ALL=1` invocations in `registry-liveness.yml`
      carry `ENGINE_PINS_ALIAS`; no other workflow sets it.

## 5. Verification (pre-push proofs)

- [x] 5.1 `make openspec-validate NAME=engine-alias-select-2987` exits 0.
- [x] 5.2 `make test-unit` exits 0 with the new tests included (4318 passed, 13638 deselected, rc=0 on the tree carrying the work record).
- [x] 5.3 Live detection proof: `ENGINE_PINS_ALIAS=1 make check-engine-pins-published ALL=1` exits red (gate rc=1, make rc=2) naming exactly the three measured lagging aliases (`edge0:cuda`, `vllm:cuda`, `vllm:rocm`) with `ALIAS LAG` + `[select]` lines — a red sweep is the green outcome at this head (the aliases still lag on `main`; the moving push repairs them post-merge, tracked by #2989).
- [x] 5.4 `make check-docs` exits 0 on the tree that carries this change's note and index row.
