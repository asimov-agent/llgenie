# Tasks

## ci.yml step guard

- [x] 1.1 `make check-pr-base` step carries `if: github.event_name == 'pull_request'`.
- [x] 1.2 The workflow comment states the real event scope (push runs skip; main moved faster
      than the gate's live fetch — issue #1867).

## Verification

- [x] 2.1 Guard test `test_the_check_pr_base_step_is_gated_to_pull_request` RED on the old tree
      (no `if:`) / GREEN on the fix.
- [x] 2.2 `make check-pr-base` still reds a foreign-base PR and passes a clean one-ahead branch
      on pull_request (the #845 negative control, unchanged).
- [x] 2.3 `make changes-index` renders CHANGES.md; `make check-docs` passes.
- [x] 2.4 `OPENSPEC:` body line names this change; `make check-pr-hygiene openspec-change` passes.
