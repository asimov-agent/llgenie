# Tasks

- [x] `.github/workflows/ci-verdict.yml` gains a `workflow_dispatch` trigger with a required `run_id` input and an optional `head_sha` input (issue #1886).
- [x] The `judge` job resolves `RUN_ID`, `HEAD_SHA` and the concurrency group key from `inputs.*` when a dispatch, else from `github.event.workflow_run` — the auto `workflow_run` path is unchanged (`CI` → `completed`).
- [x] Workflow header contract updated: the "never dispatches" comment now states the single dispatch exception (manual re-judge, read-only + check-run post; no CI re-run, no branch write, no secret read).
- [x] YAML parses clean; `tests/test_ci_verdict.py` suite passes unchanged (the `on["workflow_run"]`, `judge`-rename #1871 and check-run asserts all hold with the added trigger).
- [x] Openspec change `ci-verdict-dispatch-rejudge` (proposal + spec requirements/scenarios + tasks) validates: `make openspec-validate NAME=ci-verdict-dispatch-rejudge`.
- [x] Docs trio: `docs/changes.d/2026-11-07-ci-verdict-dispatch-rejudge-1886.md` (one table row) + `agent-wiki/2026-11-07-ci-verdict-dispatch-rejudge-1886.md` narrative + regenerated `CHANGES.md`; `make check-docs` green.
- [x] PR body carries `AGENTS:`/`BASE:` (#792), `closes #1886`; normal review flow (owner merges). No merge/arm (#1088).
- [x] On a dispatch with run_id but no head_sha input, the judge resolves HEAD_SHA from the run"s own head (GH API) and posts the check-run there — never an empty HEAD_SHA.
