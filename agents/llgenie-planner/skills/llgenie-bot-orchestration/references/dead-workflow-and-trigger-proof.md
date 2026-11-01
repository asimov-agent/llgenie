# Proving a workflow never fired (dead monitor, dead trigger, divergent trigger block)

"This monitor never runs" is a finding two different classes of evidence can support, and they are not
equal. Trigger reasoning — "its only trigger is `workflow_run` on a disabled source, so it cannot fire" — is
a hypothesis. The runner's own counters are the measurement. File the finding on the measurement and keep
the reasoning as the explanation.

## 1. `total_count` is authoritative and repo-wide, per workflow file

```bash
gh api repos/<o>/<r>/actions/workflows/<file>.yml/runs \
  --jq '{total:.total_count, recent:[.workflow_runs[]|{id,conclusion,created:.created_at,head:.head_sha[0:8]}][0:3]}'
```

- `total: 0` → the workflow has **never executed once** in its lifetime. That is the strongest statement
  available and it outranks any argument about which event ought to have fired it.
- `total: N` with the newest `recent` entry **predating the commit that introduced the consumer** → the
  trigger event never had an opportunity. That is different from "it fired and silently failed" and must be
  said that way.
- Quote the part of the head sha you printed, plus the id of anything you cite from the list.

## 2. A consumer keyed on a disabled source cannot fire — census the disabled set first

`workflow_run: [<source>]` produces no event at all while `<source>` is disabled, so no amount of retrying,
re-running or re-arming the consumer will help. Census first:

```bash
gh api "repos/<o>/<r>/actions/workflows?per_page=100" \
  --jq '[.workflows[]|select(.state=="disabled_manually")|.path]'
gh api repos/<o>/<r>/actions/workflows/<source>.yml/runs \
  --jq '{total:.total_count, last:(.workflow_runs[0]|{id,conclusion,created:.created_at})}'
```

Two facts together are the proof: source `disabled_manually` → no event exists; source `last` predating the
consumer's merge commit → no opportunity even while it was enabled. State both, and name the source workflow
and its last-run time.

## 3. Reconcile the merged trigger block against what the PR body promised

The file at the merge sha is the shipped truth; the body's promise is a claim about intent.

```bash
git show <merge-sha>:<path/to/workflow.yml> | sed -n '/^on:/,/^[a-z]/p'
```

Read the file **at the sha** (`git show <sha>:<path>`, or `git show origin/main:<path>`) — never from a local
clone's working tree, which in this fleet can be dozens of commits behind and produces a false "the file is
missing" or false drift. A body promising "scheduled twice-hourly + `workflow_dispatch`" against a file that
ships only `workflow_dispatch` is a real **trigger divergence at the merge**; report it naming the merge sha,
the promised trigger and the shipped trigger.

Remember that `schedule:` only fires from the **default branch**: a schedule that is literally correct in the
file is still dead if that file exists only on a non-default branch, and `workflow_dispatch` has no runs
unless a human clicked it — which also shows up as `total: 0`.

## 4. Classify before you file

| evidence | verdict to file |
|---|---|
| `total: 0` + source disabled | **dead by disabled source** — fix is a firing trigger (schedule/`push`/`workflow_dispatch`), not a code rewrite |
| `total: 0` + source enabled, consumer on the default branch | **never ran despite a live trigger** — file against the trigger wiring |
| `total: 0` + file only on a non-default branch | **not yet shipped** — merge/precondition problem, not a monitor defect |
| `total: N`, newest entry red | **fired and failed** — a job-level fix; expand the matrix (`references/actions-run-attempt-reconciliation.md`) |
| file's `on:` block ≠ body's promise | **trigger divergence** — file it against the merged PR, naming the sha |

Strengthening an already-filed finding with run-count evidence is a legitimate forward step: post it on the
same thread, say explicitly that the fix is unchanged and only the evidence class improved, and never re-file a
second issue for the same defect.
