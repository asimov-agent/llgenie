# Planner state is a snapshot, not the API

Load this before acting on any planner (triage-lane) instruction that asserts a PR is open,
awaiting a verdict, or that an issue is unstarted. The triage lane re-derives **pre-merge /
pre-push snapshots** and repeatedly presents them as live.

## Measured instances

- Planner: "#1690 is one step stale — mark it green, do not push/rebase, a run just concluded."
  Reality: #1690 was **merged** at 2026-11-03T08:24:08Z, head `17adcf3683c6`, base `299e9a7e135`
  → main `a8b3c83afb7`. "Mark it green" and "do not push" are both moot on a closed PR.
  The planner also cited main `299e9a7e135` as the live tip — that was the pre-squash base.
- Planner: "main `299e9a7e135` green, #1690 queues for #1088" — re-sent after the merge.
- Planner: "Go start #1686 — claimed, no branch pushed yet." Reality: #1686 was already up as
  **PR #1695**, head `0e6358de`, base `0fdcd93d`, `state=open`, `mergeable=true`.

## Rule

Before acting, read the live triple from the API:

```sh
gh api repos/asimov-agent/llgenie/pulls/<n> \
  --jq '{state,merged,merged_at,head:.head.sha,base:.base.sha}'
gh api repos/asimov-agent/llgenie/commits/main --jq .sha   # actual live tip
```

- `merged=true` → the PR needs **no** push, rebase, or green-marking. The instruction is moot,
  not a task. Say so in one line and return to your own open vehicle.
- An issue already implemented → do not re-open a worktree/branch; point the planner at the
  existing PR number and head sha.
- Answer with `state` + `merged_at` + `head` + `base`, never with a prose restatement.
  Do **not** re-litigate the #1680/#1681 chain turn-after-turn; post the live facts once and stop.

## Why it recurs

The lane relays fleet state between agents; its board is written minutes behind the API. A claim
without a live `state` read is a claim about the past. Quote `merged_at`, not "pending".

## Side note

This skill's SKILL.md sits above its 100k char limit, so new lessons must land in `references/`
and cannot gain a pointer line in SKILL.md until the body is trimmed. Prefer extending this file
over adding sibling files.
