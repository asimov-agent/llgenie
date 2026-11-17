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
- Planner: "your PR head `540c28b2`, ACs all proven, only AC5 red" for a merge-readiness confirm.
  Reality: live head was `a5168c5` — **29 commits ahead, `diverged`** from the cited head; every AC
  tick pin (`head=540c28b2 … run=42118921062`) referenced that PRIOR head. The current-head gate log
  had to be read to prove ACs re-validated there.

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

## Confirming merge-readiness: read the gate log at the LIVE head, not the cited head

A planner "confirm PR <n> is merge-ready, ACs proven" dispatch is a **read the wire and gate log**
task, never a restate-the-planner task. Verdicts and AC tick pins are head-bound (#1644): a pin at
head `X` proves nothing at head `Y` once the branch advances (a rebase or new commit moves it).

1. Read the LIVE head (`gh pr view <n> --json headRefOid,mergeable`) — never trust the planner's
   quoted sha; compare it to the tick pins' `head=` in the issue body.
2. If heads differ, read the actual `check-pr-acceptance` job log at the live head and **count the
   violations**. The gate re-evaluates the ticks against the live HEAD, so a green-aside count at the
   live head is the proof, not the stale pins.
3. Distinguish a REAL residual from the by-design **post-merge state criterion** — a final AC like
   "the PRs merge / umbrella becomes tickable / reviewer ticks it". That criterion is unchecked
   pre-merge BY DESIGN (verdict-gated #1644, cannot self-tick #1792); it is the expected single red,
   not a defect and not something a push fixes.
4. Report `mergeable`, `mergeStateStatus`, the live head, the exact AC number still `- [ ]`, and the
   gate's verbatim line. When the sole residual is the post-merge criterion, name the **owner merge**
   as the next actor; the lane stays read-only (#1088) — no push, merge, or arm.

## Close verdicts must read the OPEN PR board: implemented + OPEN PR ⇒ the issue stays open (issue #2869)

A lane close is filed `state_reason: not planned`. The other close reason, `completed`, is GitHub
closing an issue through a pull request's closing reference — and that happens only when the PR
merges. So an issue that is already implemented by work whose PR is still OPEN must NOT be closed by
the lane: closing it buries the implemented work as "not planned" while the implementing PR is still
landing. Measured on #2048: closed `not planned` at 2026-11-16T19:1x while PR #2863 — the PR whose
body closes #2048 — was OPEN and mid-flight (issue #2869).

Before any close verdict: `gh pr list --state open --limit 300 --json number,title,body` and look for
an OPEN PR naming the issue (closing keyword adjacent to `#<n>`, an `Issue: #<n>` line, or `(#<n>)`
in the title). One exists → the verdict is a **hold**: one comment naming the PR, the issue stays
open, the lane's claim is released (`bot-done`) and the queue labels come off. `scripts/issue_implementer.py`
enforces this host-side: `open_implementing_pr()` resolves every number a close verdict cites, and a
cited OPEN claiming PR converts the close into `apply_hold`.

## Why it recurs

The lane relays fleet state between agents; its board is written minutes behind the API. A claim
without a live `state` read is a claim about the past. Quote `merged_at`, not "pending".

## Side note

This skill's SKILL.md sits above its 100k char limit, so new lessons must land in `references/`
and cannot gain a pointer line in SKILL.md until the body is trimmed. Prefer extending this file
over adding sibling files.
