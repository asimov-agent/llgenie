# verdict-judged-roster — tasks

- [x] `scripts/ci_verdict.py`: read the head's check-runs (`filter=latest`, truncation refused), resolve each blocking row to its workflow through its `details_url` run, skip the judged workflow and the verdict's own `ci-verdict` row
- [x] `BLOCKING_CONCLUSIONS` is exactly `scripts/auto_merge.RED_CONCLUSIONS`, asserted equal by a test
- [x] a green judged run with an unjudged blocking check-run posts `failure`, naming the check, its workflow and its run id (`UNJUDGED RED` lines, also in the posted check-run body)
- [x] `--checks FILE` makes the read replayable; a missing head sha exits 2 and posts nothing
- [x] `scripts/verdict_roster.py`: posters (pull_request / pull_request_target), the judged roster, the difference, and every finding (`verdict-roster-{unrecorded,not-judged,undated,stale,blind}`)
- [x] `data/verdict-roster.json`: one dated decision per poster (`ci.yml` judged; `scope.yml`, `holds.yml`, `engine-build-pr-trigger.yml` not judged, each with reason/date/issue)
- [x] `make verdict-roster` (+ `.PHONY`) renders the report; `docs/BOTS.md` and the `ci-verdict.yml` header document the rule
- [x] `scripts/check_workflows.py::check_verdict_roster` wired into `findings()`, so `ci-unit` reds on an unrecorded poster
- [x] `scripts/package-layers.json` places `verdict_roster` in "Structural gates" and states the `ci_verdict -> verdict_roster` edge; `docs/ARCHITECTURE.md` §Scripts documents the target
- [x] `tests/test_verdict_roster.py` (11 tests) and 7 new cases in `tests/test_ci_verdict.py`; every refusal proven on a temp tree built by the test
- [x] AC-1: `make verdict-roster` prints posters (4) / judged (1) / NOT judged (3) as a subset check
- [x] AC-4: sabotage — a temporary `on: pull_request` workflow reds `make check-workflows` with `verdict-roster-unrecorded/<file>`, removing it returns `[workflows] OK`
- [x] AC-2 + AC-5: re-measured at the real specimen head — `make ci-verdict RUN_ID=42440650781 HEAD_SHA=aeac049f…` reports the judged run green and exits 1 naming `check 'trigger' … run=42440650801`
- [x] AC-3: negative control on a live head — a deliberately red sibling check-run is named (red), and the same check green returns a clean verdict (restored)
- [x] `make openspec-validate NAME=verdict-judged-roster` exits 0
