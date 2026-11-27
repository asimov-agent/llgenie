# Tasks: align the planner SOUL with CI-only landing

## 1. Spec first

- [x] OpenSpec change `planner-no-approval-gate-3084` created through `make openspec-new`
      with proposal, spec delta and this task list before any code edit.
- [x] The spec describes CI-only landing, no approval gate, and idle-pickup while CI is in
      flight, matching issue #3084 and the exact SOUL paragraph on PR #3085.

## 2. Land the binding on the PR branch

- [x] PR #3085's branch carries this change under `openspec/changes/` and its body names
      it with an `OPENSPEC: planner-no-approval-gate-3084` line.
- [x] The agent-wiki note `2026-11-26-planner-no-approval-gate-3084.md` and its one-row
      `docs/changes.d/` fragment are present and indexed in `CHANGES.md`.

## 3. Prove it

- [x] `make openspec-validate NAME=planner-no-approval-gate-3084` rc=0 at the named head.
- [x] `make check-pr-openspec-change` rc=0 at the named head with the live PR body.
- [x] `make check-docs` rc=0 and `make check-pr-acceptance` rc=0 at the named head; the
      implementation commit's ticked acceptance mirror and the four re-stamped proven
      clauses are preserved by the reviewer lane after any head move.
