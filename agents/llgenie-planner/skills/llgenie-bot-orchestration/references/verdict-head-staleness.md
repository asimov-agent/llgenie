# A verdict's cited head can be superseded mid-review

When a base-race rebase lands while a reviewer is composing a verdict, the verdict names the OLD head (`Accepted: all N criteria met at <old-sha>`) — still true of that sha, but no longer the PR head. Two consequences:

1. **The #1644 tick seam fires on the verdict anyway** and can clear the gate at the CURRENT head, so the outcome is often sound even though the citation is stale. Do not reject a landed tick just because its cited sha is old — measure the gate at the live head first (guard/scope/ci-verdict/holds SUCCESS = the tick cleared the self-red).
2. **The defect is the stale citation,** not the outcome. Record the caveat in the durable board record and tell the lane that future verdicts must cite the CURRENT `headRefOid`, not a head a rebase supersedes.

Before accepting any verdict: compare the verdict's sha against the live `gh pr view <n> --json headRefOid`. If they differ, note it.

Verify the tick landed via the seam, not a manual edit: the issue `updatedAt` shifts ~1 minute after the verdict comment, and the boxes read `- [x]`. A manual body edit is a violation; the seam is the sanction.

## The same staleness hits a lane's own "new head <sha>" report — a force-push moves it again

A lane reporting its latest push ("new head `af5cad79` (was `e6b1f0b4`)") is quoting the sha it believes it just
pushed; if it force-pushed again after composing the message, the live `headRefOid` is a *different* sha. Never
relay, credit, or dispatch against a head sha from prose — always read `pulls/<n>.headRefOid` fresh and use that.
Two independent facts often hide in the gap: the content may be fully landed (the `files` list shows the fix at the
true head) while only the reported sha is stale, and the PR STATE may have changed with the newer push (e.g. now
`DIRTY`/`CONFLICTING`). Resolve BOTH on the wire — head sha AND `mergeable_state` — before correcting the lane, and
correct the stale frame explicitly rather than only restating the disposition.
