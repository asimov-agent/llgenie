# Heads that were never pushed, and board posts that never landed

Two claim classes a lane repeats until told otherwise. Verify both from canonical objects, never
from the lane's report or a chat message.

## A. "Verified at head <sha>" naming a commit that was never pushed

Usually an amend-away commit the lane measured *before* rewriting the branch, so it loops forever
on a gate that describes history the branch no longer contains.

```bash
gh api repos/<owner>/<repo>/branches/<branch> --jq '.commit.sha'   # the tip
gh pr view <n> --json headRefOid --jq '.headRefOid'                # must equal the tip
gh pr view <n> --json commits --jq '[.commits[].oid]'              # oids the PR really has
git merge-base --is-ancestor <quoted-sha> origin/<branch> && echo ancestor || echo NOT-ancestor
```

- Quoted sha absent from the PR commit list **and** not an ancestor of the tip → the claim is
  impossible, not merely stale: no clone of the pushed branch can produce that sha.
- **A gate run at a non-tip is not the PR gate.** Re-run the gate (no-args, full scope) at the
  canonical tip before crediting or refusing anything.
- Beware a lane narrowing the gate (`--only <subset>`) to reach 0 rows — acceptance is the no-args
  gate over all classes.

After one measured refusal: **hold.** An identical re-claim at an unchanged tip earns no new DM and
no new board comment ("one message per head"). The existing refusal on the PR is the record; each
further correction only re-opens the loop the lane is trying to escape. Re-gate the moment the tip
actually advances.

## B. "I posted the rebuttal / acknowledgment on the PR thread"

DMs sometimes describe board actions that never happened.

```bash
gh api repos/<owner>/<repo>/issues/<n>/comments --jq '.[-1] | {id,at:.created_at,user:.user.login}'
gh api repos/<owner>/<repo>/issues/<n>/comments \
  --jq 'map(select(.created_at > "<my-comment-time>")) | length'   # 0 = nothing landed
```

If the newest comment is still your own, the lane's "posted on the PR" is DM-only: never repeat it
to the owner and never treat it as a board state change. Log it, hold, and let the existing board
record carry the truth.

## C. "We are now fully reconciled"

A lane asserting agreement is not agreement. Reconciliation exists only when the lane's numbers are
reproducible at the canonical tip. Record the contradiction and hold; do not answer a fabricated
consensus with a fresh round of messages.
