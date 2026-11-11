# Pre-relay vehicle-set + defect check

Before you relay source bytes, a "the grant/line is missing at :N" claim, or a "cut a new vehicle off main" instruction that a lane will *implement*, verify two things live — not from a prior read, not from a bot's message, not from your own memory of an earlier pass:

1. **The defect is actually present on `origin/main` now.**
   - `git log origin/main -S '<token or symbol>' -- <path>` — did it already land? (e.g. `issues: write` was present at security-scan.yml:109-114 since 2026-10-27, #717/#729, commit `82c02209`; a stale relay claimed it was "missing at :113" and pointed the lane at a wrong fix.)
   - `git show origin/main:<path> | awk 'NR>=A && NR<=B'` to paste byte-literal lines, honoring literal-preservation.

2. **No vehicle for the issue already exists.**
   - `gh api repos/<repo>/pulls/<n>` → read `state`, `merged_at`, `head.sha`, `baseRefOid`, `mergeStateStatus`.
   - `gh pr list --state open` and filter by closing issue/title.
   - If a PR already closes the issue, it *is* the vehicle. Broadcasting "cut a fresh vehicle" then creates a **duplicate** — the one-vehicle violation the planner exists to prevent. The lane's real obligation becomes "keep that PR's own-gate green", not "open a new one".

## When the set holds TWO open vehicles for one issue, collapse on measured merit

The complement of §2: sometimes the duplicate already exists — a second lane opened its own PR before you stood it down. One issue keeps one vehicle; the pick is the planner's call, not the lane's, and it is measured, not voted.

- **Read the acceptance criteria against each head, not the file lists.** Two vehicles for one fix routinely touch a near-identical file set (same script, same tests, both a change-note). File-list parity says nothing about completeness — one can stop at a partial step.
- **Diff the actual content at each head.** Get the real tip (`gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`; for a fork-headed PR fetch that head — see fork-phantom-refs-and-superseded-records.md), then `git show <sha>:<path>` and grep the discriminating symbol. Ask: does the script actually call the thing the acceptance criterion names, or does it only classify/file and never post the verdict? A classifier that files issues but omits the force-red check-run is *half* the fix.
- **Verify the permission ↔ the call.** If the winner posts a check-run, its workflow must grant `checks: write` (`git show <sha>:<workflow> | grep -n 'checks:'`). A script that POSTs a check-run under a workflow that only carries `issues: write` dies at runtime while every gate still reads green — the fix looks complete and is inert.
- **Same branch name on two remotes is TWO vehicles, not one.** A fork-headed PR and a canonical branch can share the exact ref name (`fix/<topic>`) at different shas. `git ls-remote origin` sees only the canonical one; the fork's real tip lives at `.head.repo`. A name match is not a vehicle match.
- **Close the loser with a comparison table** (per-criterion rows: what each head does and does not implement) and state plainly that the losing diagnosis was **not** rejected — its logic carries into the kept vehicle. Notify both the author lane and any reviewer that was driving the closed PR: give them the kept PR's head sha and tell the reviewer to re-point.

Never keep both "to see which wins" — two open PRs on one issue race the same branch and abandon each other. Never merge either; the collapse is a close + reroute, the merge stays owner-gated.

## Why this is in the planner's mouth specifically

The planner is the only actor that broadcasts *instructions to implement*, so a planner relay is treated as authoritative. A stale relay is more damaging than a bot's stale claim: it originates work in the wrong direction ("add the grant" when the grant exists) or in duplicate ("cut a vehicle" when one is open). Both are the planner's signature failure modes.

## Disposition when already sent

If the stale relay already left your mouth, correct it in the **same pass**:
- Re-measure live, name the exact refutation (`git log -S`, PR state).
- DM the lane a correction that says *disregard the prior instruction* and states the corrected target (vehicle already up, the true root cause).
- Post the corrected record on the issue (`gh api -X POST .../issues/<n>/comments`) so the board is the single truth, not a DM.

The fix is never to defend the stale relay or to re-send it louder — measure, correct, record.

## Concrete instance

#1598: the real defect was the `security-issues` step's `GH_TOKEN: secrets.BUMP_TOKEN || GITHUB_TOKEN` at :157 shadowing the job-scope `issues: write` grant with an owner PAT that lacks it — fixes with `GH_TOKEN: ${{ github.token }}`, which was already open as #1614 (head `ed706a01`, base = current main). The grant `issues: write` was never missing; a fresh vehicle was never needed.
