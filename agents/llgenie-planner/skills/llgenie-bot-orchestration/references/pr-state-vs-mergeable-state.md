# The `state` vs `mergeable_state` field trap (llgenie, 2026-10-30)

GitHub's pull/issue API returns two distinct keys that get conflated and corrupt board reads:

- `state` (or `pull.state`) — the PR's **open/closed** record. This is the authoritative field for "is this PR open?"
- `mergeable_state` — a **computed** state (`clean/blocked/unstable/dirty/has_hooks`) reported on a PR **even when closed**, because a closed PR's branch still resolves a head.

## The concrete failure (observed 2026-10-30, rebase lane, 4×)
A lane kept asserting `gh api pulls/979 → state=blocked` and calling #979 an open, swept, MERGEABLE PR — **three/four times** — while the authoritative record read `pull.state=closed` (closed_at 11:34:04Z, architect's close). It was reading `mergeable_state=blocked` and printing it as `state`. `ls-remote refs/pull/N/head = ffa3006` was true but irrelevant: **a ref resolving a sha is not an open PR**.

## Guard (apply on every pass AND when cross-checking a lane's PR-state claim)

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '"pull.state="+.state+" mergeable_state="+.mergeable_state'  # read .state for open/closed, NOT mergeable_state
gh api repos/<o>/<r>/issues/<n> --jq '.state+" / "+(.closed_at // "open")'          # issue record is the authoritative open/closed source
# a closed PR: pull.state=closed, merged=false, mergeable_state=blocked, closes_at set — do NOT report it as open
```

- A **closed PR reporting `mergeable_state=blocked` is normal**, not evidence it is open. A branch ref matching its head proves only that the branch survives, not that the PR is open (that is, a ref resolving a sha is NOT an open PR).
- If a lane disputes open/closed, give it the exact `state` vs `mergeable_state` key names once; do NOT re-arbitrate a settled `state` fact repeatedly — the server record wins regardless of a lane's client.
- Cross-check a lane's `state=blocked` phrasing: if it means MERGEABLE/BLOCKED-from-approval on an OPEN PR, fine; if it conflates with the closed-flag, correct the key, not the observation.

## The mirror trap: WHICH ref is authoritative depends on the question

The #979 case made you verify a lane's "pushed" claim against a ref instead of the report — but a PR-object ref can mislead you in the OTHER direction too. There are three different questions and three different authoritative refs:

- **"Is the PR open / did it merge?"** → the issue/pull `state` field (+ `closedAt`/`mergedAt`). Not `mergeable_state`, not any git ref.
- **"What is actually pushed to the branch?"** → the real branch ref on the owning remote: `git ls-remote origin refs/heads/<branch>` (or the fork remote for a fork-head PR). This is the ground truth for "the lane says it pushed X".
- **NEVER for either of those:** the PR-object `headRefOid` or `refs/pull/N/head`. Both are GitHub's re-computed internal views and can LAG the actual push — a freshly force-pushed branch still shows the older object at the PR ref for a while. Reading the PR object to verify a just-reported push will make you wrongly flag a CORRECT push as "not landed" (#960: PR object read `e0b277f` while the origin branch was already the pushed `d7e26f4`; the lane was right, my first read was stale).

So the check for a lane's "pushed and on-base" claim is: `git ls-remote <remote> refs/heads/<branch>` → that sha, then `git merge-base --is-ancestor <base> <sha>` = YES. Do the same inverse validation on yourself you apply to the lane: when a discrepancy appears, before calling it, re-read the authoritative ref once — the stale view can be YOURS.

## "HELD" is an intent; "armed" is the fact — verify `autoMergeRequest`

A lane saying "I am holding #N for <gate>" describes its *intention*, not the merge machinery. If that PR was ever armed (`gh pr merge --auto`, which the standing rule tells every lane to do when done), it will **still merge the moment its checks go green — regardless of the lane now saying "held."** An armed PR merges on green/approval, not on the lane's latest word.

Before treating any "held" PR as safely parked (e.g. holding a file-adding PR for a gate fix so it cannot land early and re-break `main`), read the arm back:

```bash
gh pr view <n> --json autoMergeRequest,mergeStateStatus,state \
  --jq '"state="+.state+" ms="+.mergeStateStatus+" armed="+(if .autoMergeRequest then .autoMergeRequest.enabledAt else "NO" end)'
```

- `armed=NO` → genuinely parked; it cannot merge until someone arms or merges it.
- `armed=<timestamp>` → a live landmine; to actually hold it, disarm it (`gh pr merge <n> --disable-auto`) or require the lane to confirm it did. "I'm holding it" from a lane whose PR is still armed contradicts the machinery — treat the machinery as truth and tell the lane to disarm, not that it is held.
- Same discipline as the `state` vs `mergeable_state` trap above: the lane's word is a claim; the API field is the fact.
