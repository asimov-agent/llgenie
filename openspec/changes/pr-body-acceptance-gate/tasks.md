# Tasks

- [x] Verify the finding: #2267 merged with all four PR-body boxes unticked and no gate reads them (issue #2352 measurement, reproduced at `6f3d65b0`)
- [x] `check_pr_acceptance.py`: add `pr_body_acceptance_findings` (sole-vehicle → unticked/tick-unprovable findings) and the `body` subcommand (REAL PR body file, plus the body+squash close set)
- [x] Makefile: `check-pr-acceptance-body` target + `.PHONY` + `##` help line, wired like `check-pr-acceptance`
- [x] ci.yml `guard` job: step `make check-pr-acceptance-body` (live PR-body read, judged job) ; scope.yml guard: same step for docs-only bot PRs
- [x] Tests: (1) #2267 four-unticked → RED, (2) all ticked with run ids → GREEN, (3) a PR that closes an issue → skipped, (4) `- [x]` with no evidence → RED — real script, real PR payload, no mock of the decision; existing test_check_pr_acceptance.py untouched
- [x] Change-note trio (`agent-wiki/`, `docs/changes.d/`, rendered `CHANGES.md`) + the make help line documented; `check-docs` / `lint` / `check-wiring` / `openspec-tasks-check` green
- [x] `make openspec-validate NAME=pr-body-acceptance-gate` green; `make lane-preflight` green
- [x] Open the ready-for-review PR against main with `closes #2352`, `AGENTS:` + `BASE:` stamps; do not merge
