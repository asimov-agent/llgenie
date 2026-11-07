# Tasks

- [x] `scripts/ci_verdict.py` gains a settle gate: when the run-id path reads a jobs list, it raises on any job with `status != completed`, naming the job — an `in_progress`/queued row is never a verdict (exit 2, no check-run posted).
- [x] The settle check runs before `ci_scope.verify()` and before the decision artifact is trusted, so a mid-upload snapshot is refused before anything is counted.
- [x] `scripts/ci_verdict.py::main()` routes the refuse-through-exit-2 through the existing error path (`FAILED: could not reach a verdict`), so the workflow surfaces it as its own failure and the run-fixer routes it.
- [x] Tests: a decided run with one `in_progress` job exits 2 and posts nothing (RED-fixed: exit 0 before the gate would be a false green). Tests: a fully settled red run still exits 1 naming the failing gate; a settled `none` (cancelled, no artifact) still exits 1.
- [x] OpenSpec change `ci-verdict-judge-waits-for-settled-run` validates: `make openspec-validate NAME=ci-verdict-judge-waits-for-settled-run`.
- [x] Docs trio: `docs/changes.d/2026-11-07-ci-verdict-judge-waits-for-settled-run-2010.md` (one table row) + `agent-wiki/2026-11-07-ci-verdict-judge-waits-for-settled-run-2010.md` narrative (`#2010`, `#<PR>`); `make check-docs` green.
- [x] PR body carries `AGENTS:`/`BASE:` (#792) and `closes #2010`; the PR is ready (never draft); no merge/arm (owner/CI lands it).
- [ ] Reported: head sha, a run id proving the judge green on a main push, and the failing-run ids tested against.
