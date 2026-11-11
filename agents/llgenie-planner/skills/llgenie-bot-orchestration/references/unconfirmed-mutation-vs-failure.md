# "Unconfirmed" / "degraded" is not "failed"

When a lane reports it could not confirm a mutation — "write-back issued but landing
unconfirmed", "my tool channel degraded", "verdict posted but I don't see it" — that is
very often a display artifact, not a proof of absence. The mutation frequently landed.

## Before re-issuing any mutation, read the object store

- **AC tick / write-back**: count `[x]` in the live issue body
  (`gh issue view <n> --json body`). Proven annotations beside each `[x]` confirm it landed.
- **Review verdict**: fetch by id and read state/timestamp
  (`gh api repos/<o>/<r>/pulls/<n>/reviews --jq '.[]|select(.id==<id>)|{state,submitted_at}'`).
- **Label / comment / branch**: fetch the object directly; never infer from a DM body.

Confirm first. Re-issue **only against a measured absence.**

## Re-issuing a landed mutation duplicates it

A transient tool/work loop can re-apply the same write on its own; duplicated pin blocks
then appear on-wire and must be stripped back to the clean set. So the check is not only
"did it land" but "did it land exactly once" — a doubled block is a cleanup, not a success.

## Same rule for a prepared-but-unpushed rebase candidate

A lane's "prepared, NOT pushed" head is a proposal, not the branch. Fetch the live wire
head and compare:

    git fetch -f origin refs/pull/<n>/head:pr<n>
    gh pr view <n> --json headRefOid,baseRefOid,mergeable

If the live head is already newer and green, the prepared candidate is **superseded** — do
NOT push it. Pushing would replace a verified green head with an unverified one (and can
reintroduce failures the live head does not carry). Treat it as moot and say so on the PR.
