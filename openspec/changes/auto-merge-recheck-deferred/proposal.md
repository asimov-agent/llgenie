# A deferral is retried, not parked

## Why

`auto-merge` fires only when a `CI` run completes, and a deferral is exit 0 **by design** (a policy decision,
not a broken gate) with one marker-deduped comment per head SHA. Nothing re-evaluates that PR afterwards, so a
blocker that clears *without a push* leaves a green PR unmerged until a human re-runs the job.

Measured on PR #541:

```
06:05Z  auto-merge run 39909407308 → deferred: "the PR's author (`asimov-agent`) is the merge token's own
        account … (or set APPROVER_TOKEN to the other allowed identity)"; run = success
06:37Z  APPROVER_TOKEN added — the blocker is gone, the PR is untouched
…       no run happens; #541 stays OPEN, green, MERGEABLE, 0 reviews
06:40Z  the run was re-executed by hand → "approving as `andyholst`", "merging PR #541", verify-closure OK
```

The same hole covers a review posted later, `do-not-merge` removed, a pending check that finished.

## What Changes

- **`recheck` in `scripts/auto_merge.py`**: lists the open PRs, and for each whose **current head** carries the
  gate's own `<!-- auto-merge: deferred <head> -->` marker, runs the SAME `run()` (approve as the other
  identity → merge → verify closure). A marker for an older head is skipped — that verdict described another
  tree — and a PR with no marker is not touched.
- **`make auto-merge-recheck REPO= [MAX=5] [DRY=1]`**, the one entry point.
- **`auto-merge.yml` gains `schedule: */30 * * * *`**, with a `recheck` job that uses
  the owner PAT and `APPROVER_TOKEN`; the existing `merge` job stays `workflow_run`-only.
- **Bounded**: at most `MAX` PRs per sweep, one line each, and the re-deferral still comments on the PR.

## Impact

- #541-style waits disappear: after the secret/review/check clears, the next sweep finishes the merge with no
  human action.
- No second merge path and no widened trust: the decision, the author gate and the head pin are unchanged.
