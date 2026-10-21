# The unit gate is hermetic: live-Hub work gets its own target

- Issue: [#438](https://github.com/asimov-agent/llgenie/issues/438)
- OpenSpec change: `unit-gate-hermetic`
- Branch: `fix/unit-gate-hermetic`

## What was wrong

Three tests in `make test-unit` left the machine: the README trend-link crawl, the vendored registry's
link check, and a real full-GGUF download of the picked model. On 2026-10-21 the download stalled for five minutes and the run still reported
`4911 passed` (`faulthandler_timeout = 300` prints a dump and keeps going — a dump is not a verdict),
taking 19:47 instead of ~13 minutes; four minutes later the same gate went red on fifteen Hub
`HTTP 429: Too Many Requests` while the tree was fine.

## What changed

- `tests/fixtures/unit-suite.json` — all three node ids are de-selected from the hermetic suite
  (`deselect`, exact node ids, each with a reason naming the target that runs it).
- `Makefile` — `make test-hub-live` (`.PHONY`, documented) runs exactly those two node ids in the test
  image.
- `tests/test_hub_live_target.py` — 4 cases: the gate's de-selection list, the target's nodes + phony,
  every de-selection still naming a test that exists, and the two node ids still defined.
- `README.md` — the hermetic rule and the new target.

## Verified

- `python3 scripts/unit_tests.py argv` now carries both node ids as `--deselect` (and no `-k`).
- `pytest tests/test_hub_live_target.py tests/test_unit_suite.py` → 17 passed.
- `make test-hub-live` → the three live checks run and pass (network + the GGUF download; see the PR).
- `make test-unit` → green, `grep -c 'Timeout ('` on its log is 0.
- `make check-docs`, `make check-wiring`, `make lint`,
  `make openspec-validate NAME=unit-gate-hermetic` — green.

## Notes

- `test-hub-live` is intentionally **not** wired into `ci-unit`: this change makes the gate honest, it
  does not newly require network in CI.
- The `faulthandler_timeout` in `pytest.ini` stays as a diagnostic; with the network tests out of the
  gate, a dump now means a real hermetic stall, which the next reader should treat as a defect.
