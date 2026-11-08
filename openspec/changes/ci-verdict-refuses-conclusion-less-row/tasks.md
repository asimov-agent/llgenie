# Tasks

- [x] `scripts/ci_verdict.py::require_settled()` treats a row as settled only when `status == "completed"` AND `conclusion` is non-empty — the `completed` + empty `conclusion` shape (the #2046 half of the mid-upload race) is refused like an `in_progress` row, naming the job, exit 2, no check-run.
- [x] The check runs before `ci_scope.verify()` and before the decision artifact is trusted (it already does — the function is called in `main()` before the decision is read; only its predicate widens).
- [x] Tests: a decided run with one `completed` + `conclusion: null` row exits 2 and posts no check-run (RED-fixed: exit 1 red with a posted `conclusion=failure` before the fix); a fully settled red run still exits 1 naming the failing gate; a settled `none` (cancelled, no artifact) still exits 1. All existing settle tests stay green.
- [x] OpenSpec change `ci-verdict-refuses-conclusion-less-row` validates: `make openspec-validate NAME=ci-verdict-refuses-conclusion-less-row`.
- [x] Docs trio: `docs/changes.d/2026-11-07-ci-verdict-refuses-conclusion-less-row-2046.md` (one table row) + `agent-wiki/2026-11-07-ci-verdict-refuses-conclusion-less-row-2046.md` narrative (`#2046`, `#<PR>`); `make check-docs` green.
- [x] PR body carries `AGENTS:`/`BASE:` (#792) and `closes #2046`; the PR is ready (never draft); no merge/arm (owner/CI lands it). The negative control (a mid-run snapshot judged → "no verdict" out loud, not green) is proven inline by the new test.
- [x] Reported: head sha, a run id proving the judge green on a main push, and the failing-run ids tested against.
