# A green, un-held docs-only PR is merged by auto-merge again (#1227)

**Issue:** #1227 · **PR:** this change's PR · **Branch:** `fix/1227-docs-pr-automerge`

## The defect (measured)

`.github/workflows/auto-merge.yml` triggered its `merge` job only on the `CI` workflow completing
(`workflow_run → workflows: ["CI"]`), but `ci.yml` skips the docs class at the trigger
(`pull_request.paths-ignore`, `scripts/ci_scope.py::DOCS_TRIGGER_IGNORE`), so a docs-only head
(diff restricted to `docs/**`, `agent-wiki/**`, `openspec/**`, `README.md`, `CHANGES.md`) **never
produces a `CI` run** — its only CI-class runs are `ci-scope` and `holds`. The merge job stayed
`skipped` even for a green, armed, un-held docs PR, and with #1088 (author `andyholst` == the only
approvable identity) no lane could approve, so docs PRs sat `BLOCKED` forever. Measured on #1222:
only `ci-scope`+`holds` runs at the head, `autoMergeRequest.enabledAt` set, every auto-merge run's
`merge` job `completed/skipped`.

## What changed

1. auto-merge now watches the **docs-class completion** too: the `ci-scope` workflow name joined the
   `workflow_run.workflows` roster (the multi-line block form, because the scope name holds a comma a
   bracketed `["CI", …]` list would mis-split; the roster still matches `name:` verbatim).
2. Because `ci-scope` runs on **every** PR and finishes well before `CI` on a code PR, a scope-triggered
   sweep must not decide a code head ahead of the green run that will itself merge it. A new step,
   `make auto-merge-channel` (`scripts/auto_merge_channel.py`), answers the one separating fact — does a
   `ci.yml` run exist at the head? — by querying `actions/runs?head_sha=…&event=pull_request&path=…
   ci.yml`. The merge step runs for a `CI` completion (as before) and for a scope sweep only when the
   channel is `=auto-merge` (a docs-only head). A 404 is a loud failure, never a guessed channel.
3. `auto_merge.py`'s `do-not-merge` guard stays the FIRST check — the human hold is never weakened.

## What was verified

- `python -m pytest tests/test_auto_merge.py tests/test_bot_pipeline_isolation.py tests/test_ci_scope.py
  tests/test_workflows_valid.py …` → 202 passed in the `llgenie/test` container.
- `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs` green; `make lane-preflight`
  green except the **pre-existing** census red (ARCHITECTURE.md census pointer `3bba736e` is not an
  ancestor of `origin/main` — unrelated to this change).
- **AC4 negative control:** removing the `ci-scope` line from the roster reds
  `test_auto_merge_watches_the_docs_class_by_scope_yml_name` and
  `test_the_merge_is_a_workflow_run_on_ci`; restoring it goes green — a future `paths-ignore` drift cannot
  silently re-exclude docs PRs without the pin redding.
- Full `make test-unit` (container, 2688 passed / 1 failed) — the single failure was
  `test_check_docs.py::…report_names_documented…` because this behavioural change owed this note (issue
  #1123); it is the change that produced this note.

## Not covered

#1222's own census re-point is its PR's separate work, not this one.
