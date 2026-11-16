# Tasks

- [x] engine-improver: move `## Working a test/CI refactor in this tree` verbatim to `references/test-ci-refactor-method.md`, link it from the body, body under 100,000 chars.
- [x] pr-rebase: move `## Fleet orchestration (issue #1010) — this skill's lane side` verbatim to `references/fleet-lane-side.md`, link it from the body, body under 100,000 chars.
- [x] planner: move `## Interrogating a filter` + `## A filter, its twin and the classifier are one set` verbatim to `references/filters-and-classifiers.md`, link both pointers from the body, body under 100,000 chars.
- [x] Per-file distinct-line subset proof prints `LOST: 0` for all three.
- [x] `tests/fixtures/skill-size-exceptions.json` carries no entry for any of the three.
- [x] Issue #2114 body updated to the measured trio (engine-improver, pr-rebase, planner-bot-orchestration) with the ci-pipelines file recorded as already under the cap.
- [x] `make check-agent-profiles` and `make check-agent-profiles-ratchet` exit 0 with no exemption in play.
- [x] `make test-unit` exits 0 at the branch head.
- [x] `make lane-preflight` exits 0 and `make openspec-validate NAME=skill-size-trio-over-cap` exits 0.
