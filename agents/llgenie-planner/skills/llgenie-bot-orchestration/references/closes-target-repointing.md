# Re-pointing a PR's closes-target after a dedicated issue is filed

## The failure this prevents

An issue is filed as an umbrella or as "the question" (#1173: are the live HF calls still inside
`ci-unit`?), then a lane is dispatched against it and opens a PR. The owner then says "create a new
issue just for this" and you file a single-purpose issue (#1174: raise the unit timeout 60 -> 120).
The lane's PR body still says `closes #1173`. If that stands, the merge silently closes the umbrella
issue whose scope was never completed, and the dedicated issue stays OPEN forever with a merged fix
sitting right next to it.

## Rule

- The PR that implements the change closes the **dedicated issue**, not the issue it was first
dispatched against. The original issue is cross-referenced as related, never `closes`.
- Filing a dedicated issue after the dispatch is a **re-point**, not a second vehicle. Do not open a
  new PR and do not re-dispatch the implementation; the same branch gets the corrected closes-line.
- Say the exact wording: "update the body so it reads `closes #<dedicated>`; keep #<original> as a
  cross-referenced related issue — do NOT close it."

## Mechanics that work

- A PR-body edit alone is enough to change the closing link, but if the closes-line lives in the
  commit message too (as in this repo's convention), the lane must `git commit --amend` and
  `--force-with-lease` its **own fresh dispatch branch**. That is in remit; a head move is expected.
- After the force-push, verify at the **new head**, never the old one:
  `gh pr view <n> --json state,isDraft,baseRefName,headRefOid,mergeStateStatus,autoMergeRequest,title,body`
  and confirm both issue states with `gh issue view <n> --json state` — the dedicated one OPEN (closes
  on merge) and the original OPEN (never cross-closed).
- The previous CI run at the superseded sha is dead; only the run at the new head proves anything.
- An auto-merge arm survives a head move in this repo, but re-read `autoMergeRequest` at the new head
  and quote `enabledAt`; `mergeStateStatus: BLOCKED` on this fleet is usually review-only (#1088),
  so judge by `mergedAt`, not by the arm's presence.

## Report shape

Accept the work only when you can quote: new head sha, the `closes #<n>` line, both issue states, the
fresh run id at the new head, and the re-read arm time. Anything less is the lane's claim.
