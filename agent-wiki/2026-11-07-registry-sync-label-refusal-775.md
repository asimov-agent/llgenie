# The registry-sync change-issue leg dies on a label write the credential refuses (issue #775)

Issue: [#775](https://github.com/asimov-agent/llgenie/issues/775). The weekly
[registry-sync](.github/workflows/registry-sync.yml) `State what changed in ONE issue` step died on
run 42362469027 (dispatch, head `6940f9e7`, 2026-11-07 10:07Z) with

```
RuntimeError: gh api -X POST repos/asimov-agent/llgenie/issues/1961/labels -f labels[]=agent:implement
  failed: gh: Resource not accessible by personal access token (HTTP 403)
```

`scripts/registry_change_issue.py::set_labels` treated every failed `gh` call as fatal, so an HTTP
403 from the runner's PAT (BUMP_TOKEN, which cannot write this label) raised out of `open_issue`,
the step exited 1, turned the job red and — because the `Open / update the sync PR` step is gated
`steps.diff.outputs.changed` without `always()` — **skipped the sync's actual PR**.

## What was verified

This is the #724/#819 class: labels through the runner's PAT are unreliable. #826 moved the write
to the REST endpoint and reads it back; what it did not do is survive the write being REFUSED
outright (403) rather than silently dropped.

- The refused-write death is reproduced by a fake `gh` whose label POST exits non-zero naming
  `Resource not accessible by personal access token (HTTP 403)` — the pre-fix script raises and the
  step dies (guard-proven: the new regression test
  `test_a_change_issue_survives_a_label_write_the_credential_refuses` FAILS on the old tree).
- The fix catches that exact refusal: prints one loud `stderr` line naming the issue + reason and
  returns, so the change issue stays filed, the leg survives and the sync-PR step still runs. Any
  other gh failure still raises.
- The #819 silent-drop red is untouched: `test_a_change_issue_that_cannot_be_labelled_fails_the_step`
  still passes (a write that EXITS 0 but is absent on read-back still `SystemExit`s).

## Key decisions

- A refused 403 is a credential fact — it will not fix itself on retry — so dying on it throws away
  the PR the run exists to produce; the leg must warn and defer, never die.
- Defect (a) of the same run (7 registry key losses vs `HEAD:data/models.json`) is NOT changed here:
  it is already resolved by the merged #1981 store follow, which landed the `2026-11-04T15:29:04Z`
  store — `make sync-registry` is unchanged and `make check-registry` is green at the current head.
- The same 403 on the `Spawn one tracking issue per NEW unskilled engine` leg
  (scripts/engine_skill_gap.py) is deliberately left a red (its unlabelled per-engine issue routes
  work to nobody, #819) and is out of scope for this change.

## Status

Script + regression test + openspec change + this note land in one PR closing #775.
`.github/workflows/registry-sync.yml` and all registry data are unchanged.
