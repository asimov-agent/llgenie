# Agent-profile fold cascade (live → tree)

When a lane's live profile drifts from the reviewed tree, the fix is a **fold PR** that copies live content into `agents/<lane>/` byte-identical. The cascade rarely converges in one round — run it as a disciplined chain.

## Rules

1. **One fold vehicle per lane at a time.** Do not open a second fold PR while the previous one is open. File the next residual as an issue with an explicit "do not dispatch while PR #N is open" clause, claim it, and dispatch only on the previous PR's merge.
2. **Bind to branch-time live, not the dispatch-time sha (#1273).** A fold binds to the sha measured at dispatch; if live grew between dispatch and branch time, fold the CURRENT live. A blob cannot be partially folded, so `agent_profile_sync --check` rc 0 at the head is the proof, not byte count matching the dispatch measurement.
3. **Mid-run growth is the NEXT vehicle, not this one.** Every fold leaves a small residual: live keeps growing after the fold (e.g. `+784 B` in `fold-residual-and-corrections.md`). Record the new blob sha (git blob + size) in the PR/report and file it as the next round's issue. Do not try to fold the growth into the in-flight PR.
4. **Never grow the SKILL body in a fold.** Fold reference files only; the SKILL body stays at its existing blob sha — the body has a size ceiling (~100 KB) and folds are reference-only.
5. **Clean vs moved main = no rebase (#1015).** A fold branched off an older sha while main moved on is fine if `merge-tree` is clean — verify merge-tree, not recency, and do not demand a rebase.
6. **A merged vehicle's pending legs are not a re-verify debt.** `linux/unit`/`linux/install` pending at merge (owner latitude) do not owe a re-run on the merged fold (see #1317/#1335); the deciding evidence is tree blob == live at the new main. Quote the lane's own completed standalone run, never the merge event (#1309 pattern).

## Verification of a fold PR (planner)

```bash
gh pr view <n> --json state,headRefOid,baseRefName,mergeStateStatus,files
gh pr view <n> --json body --jq '.body|contains("Closes #<issue>")'
gh api repos/<repo>/contents/agents/<lane>/skills/<skill>/references/<file>?ref=<head> --jq '.sha'   # == reported live blob
gh api repos/<repo>/contents/agents/<lane>/skills/<skill>/SKILL.md?ref=<head> --jq '.sha'           # unchanged
gh pr list --state open --search '<issue>'   # one vehicle only
```

A fold PR that is `UNSTABLE` with only the long `linux/unit`/`linux/install` legs `IN_PROGRESS` and every other leg green is sound — the block is the deciding leg plus the owner approval (#1088), not a defect.

## Don't re-record what is already filed

Before a lane "records the next residual", check whether the planner already filed it — a mid-run growth noted in the lane's report is typically already an issue. Send a one-line FYI with the issue number so the lane does not file a duplicate vehicle.
