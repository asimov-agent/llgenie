# Task List for orchestrator-tick-claim-liveness

## Tasks

- [x] Add requirement+2 scenarios in `specs/orchestrator-tick/spec.md` proving the dispatch releases a
      dead run's claim and still gates a live one (per issue #1959's acceptance criteria).
- [x] In `scripts/orchestrator_tick.py::measure()`, pass `is_live` (wired to `bot_claims.run_is_live`)
      to `bot_claims.occupied` and `bot_claims.released`, and print the measured release (run id) when
      a claim is freed by run conclusion instead of the marker TTL.
- [x] Extend `tests/test_orchestrator_tick.py` with the measured #1901/#1926 case driving both the
      dispatch model (emits IMPLEMENT-READY for a dead run's claim) and the bot_claims reader
      (`occupied(..., is_live=...) is None`), plus the belt case that a live run still gates.
- [x] Update the audit-dispatch source (`agents/llgenie-planner/skills/github-issue-triage/references/
      bot-claim-and-branch-sweep.md` and its SKILL.md pitfall) so claim liveness is read from run
      status first and the release (run id), not the marker TTL, is reported.
- [x] `make openspec-validate NAME=orchestrator-tick-claim-liveness` exits 0.
- [x] Fast gates pass (`lint`, `check-claim-reader`, `check-docs`, `check-workflows`, `check-wiring`).
