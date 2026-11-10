# Dispatch premises and workflow admission

## Measure a dispatch premise against current main before building

A dispatched task can carry a **pre-merge base** (`build X from origin/main@<sha>`): the sha names the
base the work would branch from, not the state of main today. That work may already be merged and
green. Before creating any branch or worktree, measure:

```
git fetch upstream main && git rev-parse upstream/main
git show upstream/main:.github/workflows/<workflow>.yml     # does the target already exist?
gh pr view <pr> --json state,headRefOid,mergeCommit,autoMergeRequest
```

If the artifact already exists byte-identically and its gates pass at the merged head, a stale
dispatch is **not a rebuild instruction** — report the measured state (file contents, passing gate,
head sha) to the planner and open no duplicate vehicle. Rebuilding a landed pipeline creates a twin
PR and re-litigates a settled change. A dispatch that names an old sha is a claim about when it was
written, not an order to reproduce that tree.

## A dispatchable workflow's actor gate is covered by the file-derived census

`tests/test_workflow_guards.py` derives `_dispatchable()` **from the workflow files themselves** and
asserts:

- every dispatchable workflow carries the byte-identical guard body;
- the guard checks BOTH `github.actor` and `github.triggering_actor`;
- the `case` arm accepts exactly `admin|maintain|write` — read from the decision arm, not prose
  substrings (a substring check is satisfied by `admin|maintain|write|read` and cannot catch the
  regression it exists for);
- every `guard` job is `needs:`-ed by a consumer (a guard nothing depends on is decoration);
- the guard-site count equals `len(_dispatchable()) + 1` (the +1 is `ci.yml`, guarded but not
  dispatchable).

So a newly added dispatchable workflow is **structurally admitted by construction** — do NOT
hand-write a bespoke guard test for it. Prove inclusion by running
`pytest tests/test_workflow_guards.py` and confirming the derived-count assertion still passes; if
the new workflow drifted from the shared guard body, checked only one actor, or widened the arm,
that one test reds. Copy the guard body **verbatim** from an existing guard site — never re-derive
it, or the byte-identical census breaks.

## Manual path gating for a cleanup / mutation workflow

When a workflow both runs on a cron and can mutate on manual dispatch:

- `APPLY` (or the delete input) is a `workflow_dispatch` input defaulting to false/report-only; the
  cron/schedule actor has no way to set it, so a scheduled run never mutates silently.
- the mutating job is `needs: [guard]` so the actor gate always runs before any deletion;
- the guard is the repo's shared byte-identical body (owner / write-level collaborator /
  `github-actions[bot]` only on a same-repo head, else refused).
