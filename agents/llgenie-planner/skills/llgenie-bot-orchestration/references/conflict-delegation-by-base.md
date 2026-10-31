# Delegating PR-conflict resolution: classify by BASE first

When the owner says "go over the PRs and resolve the conflicts / fix the red pipelines," the pass is a
**per-PR scan that classifies before it dispatches** — do not hand the whole DIRTY board to the rebase lane.

```bash
# per open PR, read ms + base (batch in one call)
gh pr list --state open --limit 60 --json number,mergeable,headRefName --jq '.[]|"#"+(.number|tostring)+" "+(.headRefName)'
gh pr view <n> --json mergeStateStatus,baseRefName --jq '(.mergeStateStatus)+" base="+(.baseRefName)'
# completed reds at a head (NEVER an in-progress run)
gh api repos/<o>/<r>/commits/<head>/check-runs --jq \
  '[.check_runs[]|select(.conclusion=="FAILURE"/"CANCELLED"/"TIMED_OUT")|.name]|join("; ")'
```

## The base is the owner decision

A PR's base decides WHICH lane owns its conflict state:

- **base = `main` + `CONFLICTING/DIRTY`** → genuinely the rebase lane's job (rebase onto current main,
  union/drop additions, one `--force-with-lease` push + freeze, ``cleared-to-MERGEABLE is a stop``).
- **base = another open PR's branch** (a stacked child) → NOT the rebase lane's work. Its `DIRTY` is
  base-advance from the parent's own rebase, not a defect. It retargets/re-bases when the **parent**
  lands; rebasing it against main now is chasing a moving base and risks a `#1015`-forbidden re-work.
  The parent merge is the unlock — put it on that lane, not the sweep.
- **base = `main` + `MERGEABLE`/`BLOCKED`** → not a conflict; it is the owner-approval gate
  (bot identity cannot approve, so it waits on the user). Do not re-dispatch a rebase for it.

So the scan's first step is to **bucket by base**: the genuinely-actionable set is only
`base=main ∧ CONFLICTING`. Stacked children are reported as retarget-when-parent-lands, never handed
to the rebase lane.

## Extend the live task, never re-spawn it

If a rebase task is already running, new base=main conflicts that appear after it started (main moved
again, or a previously-clean PR flipped DIRTY when its base retargeted) are **added to the same task** —
message the lane to extend its sweep (rebase order, root-first), do NOT create a second task launcher.
A second dispatch on the same conflict set is the two-vehicle failure mode.

## `mergeStateStatus = UNKNOWN` is NOT a verdict

Right after a force-push (or when main moved under a batch of PRs), GitHub re-computes mergeability and
reads `UNKNOWN`/empty for a while. That is a recompute storm, not a board change: do not quote `UNKNOWN`
as MERGEABLE or as DIRTY, do not dispatch a rebase off it. Re-measure once GitHub settles — the state
that matters is a settled MERGEABLE/BLOCKED/DIRTY or a completed run. A scan that lists only `UNKNOWN`
values across PRs found nothing actionable, not nothing-at-all.

## A clean scan is a truthful result

If no open PR head carries a completed red and the only DIRTYs are the owned in-flight rebase/stack
class, the pass has nothing to delegate *for failure* — say so plainly and state the trigger that remains
armed (completed FAILURE/CANCELLED/TIMED_OUT at any head ⇒ attribute to the owning lane + dispatch with
the failing job name, head sha, and what ``fixed`` means). Inventing a red from an in-progress run is
the exact fabrication the discipline forbids.
