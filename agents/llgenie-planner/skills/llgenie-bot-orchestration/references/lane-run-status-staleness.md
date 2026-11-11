# A lane's RUN-STATUS claim is as stale as its head claim

A settling lane describes the CI runs its push triggered as "in_progress" / "pending". That is a
claim about the instant it looked; CI completes in minutes, and the runs have usually already
finished by the time you read the settle.

## Check

    gh run view <id> --json databaseId,workflowName,status,conclusion,headSha

Do this per run, at the head the lane names — never repeat "in_progress" without it.

## Seen in practice

A rebase lane reported "fresh CI @<head>: CI <a>, holds <b>, ci-scope <c> in_progress, trigger
<d> pending". Re-measured live two minutes later: `a` = completed/**failure**, `c` =
completed/**failure**, `b` = success, `d` = pending (a waiter only). The lane had carried a
false "pending" into the chain.

## Do not misread a designed gate as build breakage

Both reds failed on the *same step*: `make check-pr-acceptance` — "a merged PR must close an
issue whose own acceptance criteria are checked". When the PR closes issues whose criteria
aren't all ticked (e.g. 2/5 + 1/3), that gate is RED BY DESIGN. It is not a rebase defect and
not a fold regression. Routing it to the rebase lane to "fix" wastes a run.

The unblock is the owner's standing rule, and belongs to the reviewer/owner, not the rebase lane:

1. Tick the criteria that are now provable (verdict-gated write-back), and
2. Name the rest under `## Not covered` with a linked work item.

Runtime criteria that need a green witness at the head the gate is blocking are the chicken-and-egg
case — surface it plainly; do not tick on faith and do not stamp the head green.

## Related

- `references/verifying-lane-claims.md` — head/pre-push staleness, the broader claim-vs-evidence rule
- `references/byte-identity-verification.md` — proving a lane's "prepared" sha IS the pushed ref
