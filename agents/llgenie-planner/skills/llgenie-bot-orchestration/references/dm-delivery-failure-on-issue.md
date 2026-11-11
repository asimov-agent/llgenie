# DM delivery can fail silently — post adjudications on-issue

## Symptom

You dispatch an adjudication/directive to a lane via `message_agent` and it returns `{status: queued}` or a settled receipt, but the lane keeps re-asking the same question across turns ("standing by for the adjudication", "the awaited decision is X"). Each reply is a fresh `settled` delivery that never carried your message. This is a degraded host read channel, not a lane ignoring you.

## Rule

The durable authoritative channel is an **on-issue comment** (or PR comment), not the DM. When a lane re-asks something you already sent, do NOT send the same DM a fourth time — that is ping-pong noise over a broken pipe.

1. Post the adjudication as an issue/PR comment on the vehicle itself (e.g. `gh issue comment <n> --body-file`). Quote the exact comment URL/id back to the lane so it can read it in its own thread regardless of DM delivery.
2. The lane reads its own issue thread, so the comment reaches it even when the DM pipe is down.
3. A lane re-asking "adjudication owed" is the tell that it never received the DM — answer by pointing at the on-issue comment id.

## Why it matters

silence between lanes on one issue is how a green gets discarded twice. A DM that returns `queued`/`settled` is not proof of receipt — the API receipt is, and the issue thread is the API receipt for a lane.

## The other half: stop replying once it is received

After the lane confirms it read the on-issue comment (`gh api` verified, not "the DM says so"), every further `settled` echo that restates the same hold is **closure, not work**. Do not answer it, do not re-send the directive, do not re-echo the adjudication — a settled echo carries no new state and a reply only restarts the loop. Answer only when an echo changes the picture (a new head sha, a verdict landed, a claim released) or contradicts the wire.

## Never let phantom scratch files drive a dispute

When a lane says the marker files you cite "do not exist anywhere", check disk once and then drop it: scratch/marker files in a lane's worktree are routinely cleaned up, so "exists now" is the only claim that can be settled. Do not argue about who deleted them. What matters is the lane's **fresh measured re-run** of the real suite (real RCs, quoted command) — take that as authoritative over any stale marker, and move the acceptance to the live CI run at the head.
