# ci-scope-verdict

- [x] `scripts/ci_scope.py`: `decision()` (schema 1), `normalise_job_name()`, `verify()` (green/red/none with `skipped-by-decision` counted separately and the `linux` caller row never counted), `check_run_payload()`, `EXIT_NO_VERDICT`; `--decision-out` writes the decision; `classify()`, the class table and the empty-diff/unknown-path contract untouched
- [x] `scripts/ci_verdict.py`: the consumer — reads run + jobs + the `ci-scope-decision` artifact through `gh` (`CI_VERDICT_GH` for a test), SUPERSEDED tested per (workflow, branch) as `scripts/ci_requeue.py` does, exit 0 green/neutral, 1 no verdict, 2 unreachable, and writes the `POST /check-runs` body
- [x] `ci.yml` `guard`: `make ci-scope BASE=<base.sha>` (or `ALL=1` on a push) + `ci-scope-decision` upload with `if-no-files-found: error`; no job-level `if:` added
- [x] `.github/workflows/ci-verdict.yml` (`workflow_run` on `CI`/`completed`, per-run concurrency, `cancel-in-progress: false`, `checks: write`, posts the check-run) and its row in `run-failure-reactor.yml`'s roster
- [x] `Makefile`: `ci-scope` gains `BASE=`/`ALL=`/`DECISION=`; new `ci-verdict`; both in `.PHONY`
- [x] `tests/test_ci_verdict.py`: 19 cases across the four answers, the caller/placeholder names, the CLI exit codes, the stub-`gh` API path, and the workflow wiring
- [x] Negative control: planted `verdict = GREEN` for a missing decision → 5 failed / 14 passed with 9 assertions firing; restored → 19 passed
- [x] `agent-wiki/2026-10-30-ci-scope-verdict.md` + `docs/changes.d/` fragment; `docs/BOTS.md` documents `make ci-verdict`
- [x] `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs`, `make check-pr-hygiene` and `make openspec-validate NAME=ci-scope-verdict` green
