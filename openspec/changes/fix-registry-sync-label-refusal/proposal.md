# fix-registry-sync-label-refusal

## Why

The weekly `registry-sync` workflow keeps failing in class #775. Run `42362469027`
(dispatch at head `6940f9e7`, 2026-11-07 10:07Z) showed two independent defects:

1. `check-registry-keys` reds on 7 registry key losses vs `HEAD:data/models.json` — the
   additive-only guard doing its job. That defect is now **resolved at the current head** by the
   merged #1981 store follow: the live upstream store (`2026-11-04T15:29:04Z`, 117 models) and
   the committed one are the same again, so `make sync-registry` reports unchanged and
   `make check-registry` is green. No registry content is touched by this change.
2. The `State what changed in ONE issue` step dies on a label write the credential refuses:

   ```
   RuntimeError: gh api -X POST repos/asimov-agent/llgenie/issues/1961/labels
     -f labels[]=agent:implement failed: gh: Resource not accessible by personal access token (HTTP 403)
   ```

   `scripts/registry_change_issue.py::set_labels` treats every failed `gh` call as fatal, so an
   HTTP 403 from the runner's PAT (BUMP_TOKEN, which cannot write this label) raises out of
   `open_issue`, the step exits 1, and because the change-issue  step's failure turns the job
   red, the `Open / update the sync PR` step (gated `steps.diff.outputs.changed`, no `always()`)
   is **skipped** — the sync's actual PR is lost for a label that was never going to stick.

The #724/#819 class is exactly this: labels through the runner's PAT are unreliable. #826 moved
the write to the REST endpoint and reads it back; what it does not do is survive the write
being **refused outright** (403) rather than silently dropped. A refusal is a credential fact —
it will not fix itself on retry — so dying on it throws away the PR the run exists to produce.

## How

- In `scripts/registry_change_issue.py::set_labels`, catch the **refused-write** case: the
  POST to `repos/<repo>/issues/<n>/labels` exits non-zero naming `HTTP 403` / `not accessible
  by personal access token`. Print one loud `stderr` line naming the issue and the reason,
  then return without raising — the change issue is already filed, the leg survives, and the
  sync-PR step still runs.
- Every other gh failure still raises (a real transport/CLI fault remains fatal).
- The **silently-dropped-write** branch (POST exits 0 but the read-back shows the label
  missing) stays a `SystemExit`: that is the #819 designed red — a change issue that exists
  but carries no queue label routes the store review to nobody.

## Benefits

- A registry-sync whose PAT cannot apply labels still files the change issue AND reaches the
  `Open / update the sync PR` step: the weekly sync keeps producing its PR instead of the PR
  being silently skipped whenever a credential refuses a label.
- The #819 routing red is intact: a write that *claimed* success while the read-back shows no
  label still fails the step loudly, never a quiet green.
- The additive registry guard is untouched: no data, key, post or stated footprint is removed
  or widened here.

## Not covered

- The same 403 also dies on the `Spawn one tracking issue per NEW unskilled engine` step
  (`scripts/engine_skill_gap.py::set_labels`, the same curl failing at line 399 of the run).
  Its design deliberately treats an unlabelled per-engine tracking issue as a loud red (#819),
  and this change does not weaken it — it is a separate work item owned by the tracker.
- The 7 registry key losses defect (a) of the same run are resolved by the merged #1981 store
  follow, not by this change.
