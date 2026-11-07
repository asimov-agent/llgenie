# Defending against a stale re-dispatch of an already-merged issue

A planner/dispatch lane can re-send an assignment for an issue whose PR you already merged, citing the issue as "open, unassigned, no PR" and a base sha hours stale. This is the ghost-loop the merged guard documents. The failure mode is endless re-litigation; the correct response is bounded.

## The bounded loop (do exactly this, then stop)
1. **Measure state at the source, once, from the API — never from the dispatch or a label.** `gh issue view <n> --json state,closedAt --jq ...`, `gh pr view <pr> --json state,mergedAt`, and `git ls-remote origin refs/heads/main`. Labels/`agent:implement` and quoted shas in the dispatch are NOT state.
2. **If the issue is CLOSED and the PR MERGED, you cannot claim or open a PR.** Claiming an unclaimed vehicle on a closed issue, or re-adding files already on main, is #824 fabrication and re-cutting a read-only merged PR. Refuse.
3. **Post ONE refusal on the authoritative channel the dispatcher names** (usually the issue thread), with the measured timeline: close time, merging PR + squash sha + head, the ls-remote main tip, and proof the scope is already on main (`git ls-tree origin/main` = N/N). Name the stale trigger (residual label on a closed issue).
4. **Stop.** No second DM, no second on-issue comment, no repeated measurement. Further echoes get no reply — replying is the ping-pong.

## Two attribution traps that manufacture the "cross-wire"
- **All bot comments post under the shared `andyholst` gh auth.** Comment `user.login` is `andyholst` for planner, implementer, and human alike, so authorship does NOT tell you who wrote it. Do not infer "the human owner said X" from `.user.login`.
- **A hand-off comment is correct *when posted*.** Compare the comment's `created_at` to your claim/PR-open/merge times: an assignment posted at T0 while the issue was genuinely open is superseded by the merge at T0+Δ, it is not a live assertion. Quote those timestamps in the refusal.
- A dispatcher claiming "the implementer keeps saying #<other>" when you never said it is a receive-side rendering defect on their side; state the fact once and do not chase it.

## A gate-red diagnosis is bound to the head it was measured at
A dispatcher/peer can hand you a *specific* gate diagnosis and a prescribed fix
("guard reds on `check-pr-sync-line`; add `SYNC: …`; rerun the failed job") measured at a head
you have **already advanced past** — often your pre-rebase sha. Do not apply the fix on the
strength of the diagnosis alone. Before editing or re-running anything:

1. Read the PR's live `state`, `mergedAt` and current `headRefOid` — if MERGED, the diagnosis is
   moot and no fix is owed (see the bounded loop above).
2. Read the **named gate step's own conclusion at the live head**: `gh api
   repos/<o>/<r>/actions/runs/<run>/jobs --jq '…select(.name=="guard")…steps[]|select(.name|test("sync"))'`.
   If that step already shows `success`, the prescribed fix is already in place — the diagnosis
   was against a superseded tree, not a live red.
3. Reply once with that step conclusion + the live head, then stop; never re-apply a fix that is
   already green, and never edit a merged/read-only vehicle to satisfy a stale diagnosis.

The trap is subtle because the diagnosis is *correct for its head*: the guard genuinely reds
when the SYNC line (or AGENTS:/BASE: line) is absent. Confirm presence/absence in the **live** body
(`gh pr view <n> --json body | grep -E '^SYNC:|^AGENTS:|^BASE:'`) rather than trusting either the
diagnosis or your memory of the last edit.

## Command shapes
```bash
gh issue view <n> --repo <o>/<r> --json state,closedAt --jq '{s:.state,c:.closedAt}'
gh api repos/<o>/<r>/issues/<n>/timeline --paginate --jq '[.[]|select(.event)|{e:.event,c:.created_at}]|map(select(.e=="closed" or .e=="reopened"))'
gh pr view <pr> --repo <o>/<r> --json state,mergedAt,mergedBy,headRefName --jq ...
git -C <repo> ls-remote origin refs/heads/main   # authoritative main tip, immune to local fetch shadow
```
