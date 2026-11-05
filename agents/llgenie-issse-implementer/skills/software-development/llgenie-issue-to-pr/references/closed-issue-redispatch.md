# Closed-issue re-dispatch (the phantom vehicle)

A planner/triage queue can re-dispatch an issue **by number** long after it is
closed and its PR is merged, because a residual label (`agent:implement`) stays
on the closed issue. The queue's snapshot then reads "open/agent:implement/
unclaimed" while the live API says `CLOSED` — the label survived the close.

## Rule

**Verify the issue's live state before any claim, and refuse a closed/merged
number.** One command decides it:

```
gh issue view <n> --repo asimov-agent/llgenie --json number,state,title,labels,assignees
```

`state=CLOSED` (even with `agent:implement` still on it, even with
`closed_at` from earlier today) means there is no vehicle: the PR merged, the
issue closed, the branch is read-only forever (#824). Claiming it again — or
"re-opening" it to make a claim true — is a fabricated board entry, not work.
Cross-check with the merged PR: the squash sha should be the current main tip
and the seam file present on main; if so the deliverable already landed.

## Symptom: the ghost-loop cites a DIFFERENT head each wake

The same number comes back across wakes, each time naming a *different* head
(`211cf460`, `a95814c50a`, `788d13ff`, ...) and a base sha that is itself hours
stale. The cited head is often a CLOSED duplicate's head, or a stale orphan ref
left on `refs/heads/<branch>` AFTER the merge tore the branch from its merged
tip — not the merged PR's real head. Measure and quote the truth:

```
gh pr view <n> --repo asimov-agent/llgenie --json state,mergeCommit,headRefOid,baseRefOid
git ls-tree origin/main <each file the dispatch wants>   # already on main = landed
git rev-parse origin/main                                 # after explicit fetch, never a chat sha
```

`state=MERGED` + the dispatch's files already in `git ls-tree origin/main` = the
exact work it asks for is done. Name the head-orphan confusion explicitly ("your
cited head is #<dup>'s head / an orphan ref, the merged head was <headRefOid>")
so the queue-owner can re-sync, then hold. Do NOT prune/delete their orphan ref —
the branch ref is the other lane's workspace; report it, never `push --delete` it.

## Handling the loop

- State the measured facts **once** with the literal command output (state,
  `closed_at`, merged squash sha, file on main).
- Set an explicit boundary: "no further reply on this number unless you bring a
  fresh dispatch whose API `state` is `open`." Then **hold it** — re-answering
  each re-dispatch of the same number is ping-pong, not diligence.
- Tell the queue-owner the fix is on **their side**: drop closed issues from the
  dispatch set; do not re-offer a `CLOSED` number because a stale label remains.
- This is distinct from declining a live-but-foreign-head PR: a genuinely open
  issue you refuse is a scope/ownership call; a closed number is a nonexistent
  vehicle. Do not conflate them.

## Three measurements that settle it fast

- **Title-search misses the vehicle.** `gh pr list --search '<n> in:title'`
  returns nothing when the merged PR's title carries no issue number (e.g.
  `fix(check-pr-base): measure against freshly-fetched main...` closed #1734).
  Prove the merged vehicle by state, not title:
  `gh pr list --state merged --json number,title,mergedAt --jq '.[]|select(.mergedAt)'`
  and `gh pr view <n> --json state,mergeCommit`.
- **Prove there is NO open vehicle.**
  `gh pr list --state open --json number,closingIssuesReferences --jq '[.[]|select(any(.closingIssuesReferences[]?; .number==<n>))]|length'`
  must be `0`. A queue that claims "no open PR closes it" is describing the
  closed issue, not an open one.
- **Bots share one GitHub account, so "no implementer comment" is refutable.**
  All bot posts land under the same login (`andyholst`); the queue cannot tell
  its own claim from mine by author. Use the *sorted comment stream*:
  `gh api repos/asimov-agent/llgenie/issues/<n>/comments --paginate --jq '[.[]|{i:.id,u:.user.login}]|sort_by(.i)|.[-6:]|.[]|[.i,.u]|@tsv'`
  — my claim/finish/closure comments have ids *greater* than the queue's
  claim marker, proving I acted after it. Quote the ids.

## Symptom: "NO branch, NO PR — claim it" on an issue that already has a green PR

A live (not closed) issue can be re-dispatched as unclaimed when its vehicle
**already exists and is fully green**. The dispatch says "no branch, no PR,
claim it, implement"; the wire says otherwise. Before claiming or writing a
single line, prove the vehicle's live existence:

```
gh pr list --repo asimov-agent/llgenie --search '<n> in:title' --json number,state,headRefName
gh pr view <pr> --json state,headRefOid,mergeStateStatus,mergeable
gh pr checks <pr>          # every line pass? mergeable_state blocked is the review/owner gate
```

An OPEN PR, head at the dispatched issue, all checks `pass`, is the deliverable —
re-implementing it produces a duplicate branch and a fabricated second vehicle.
`mergeable_state=blocked` with `review_decision=null` and no fail/pending check is
the required-review / owner-merge gate (#1088/#491), NOT a red — say so explicitly
and do not "fix" it. The only real remaining ask is the **reviewer's COMMENTED
verdict** on the issue per the #1796 shape; name that, refute the "claim it" with
the PR number + head + green-check count, and hold. Do not re-claim, do not arm.

This is distinct from the closed/merged phantom above: there the vehicle is gone;
here the vehicle is present and green and the *dispatch's premise* is stale.

**When the DM queue re-sends the same stale premise across several turns** (the
planner processes its outbox out of order and keeps citing a pre-claim snapshot),
do not answer each DM — that is ping-pong. Make the correction DURABLE where the
planner is meant to re-read: post ONE comment on the ISSUE (with PR number, head
sha, green-check count, and the start/finish bookend ids), then ONE pointer DM
naming that comment id, then hold. The issue thread — not the DM queue — is the
authoritative record; a correction that lives only in a DM does not exist for the
next reader.

## Don't fabricate work to satisfy a "do something" nudge

When the only vehicle you were given is merged and read-only, the honest report
is "deliverable landed, holding" — not a manufactured mutation on a dead branch.
