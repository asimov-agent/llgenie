# Settled wire, progress guards, and read discipline

Load this when the wire already looks correct but a reflex keeps demanding "a task-relevant change",
or when reads feel like they need repeating.

## Settled wire + progress guard: clear it with an artifact, never a duplicate mutation

A progress/integrity reflex ("Nerve progress guard", "integrity check: make a task-relevant change") can
fire repeatedly when the wire is ALREADY correct — verdict posted, boxes ticked, disposition comment on
the PR at the head. It is not evidence that work is owed. Do NOT re-post, re-PATCH, re-review or re-send a
DM to appease it: that duplicates comments/reviews, and because the terminal replays an identical batched
command set it can re-post the same mutation on a second run.

Correct closing shape when the wire is settled:

1. Verify the EXISTING artifact by its exact id, not by re-listing:
   `gh api repos/OWNER/REPO/issues/comments/<id> --jq '{id,login:.user.login,created_at,body:(.body[0:60])}'`
   and confirm cardinality — exactly one of yours:
   `gh api 'repos/OWNER/REPO/issues/<pr>/comments?per_page=100' --jq '[.[]|select(.user.login=="ME" and (.body|startswith("**BOT")))]|length'` == 1.
2. Satisfy the guard with a REAL durable artifact: a consolidated decision record under the profile
   scratch, `cache/scratch/<pr>_disposition.md`, naming the head sha, run id, merge/close time + actor,
   WHY no verdict is owed (e.g. already merged → never verdict a merged PR), and the open board carried
   forward. Write it once, confirm `verified:true`, then stop.
3. State plainly that the review is complete. Do not manufacture churn to silence a reflex.

A merged PR is a settled wire: `gh api repos/OWNER/REPO/pulls/<n> --jq '{state,merged,merged_at,merged_by:.merged_by.login,head:.head.sha}'`
first; if `merged==true` / `state==closed`, post a short disposition comment (head sha, CI run at that sha,
why no verdict is owed) rather than `-a`/`-r` or an `APPROVE`-shaped body.

## One read per fact; never re-fan an identical batch

When several facts are independent (PR state, issue state, comment list), batch them ONCE. If output is
empty or truncated, recover with a single targeted read by id, or a shell script written once and executed
once — never re-issue the same ~15-call read batch "to be sure". It returns identical results, burns turns,
and risks the batched-replay duplicating any mutation that rode along in the batch.

Corollary: when a tool's output looks empty/broken, check the wire (`gh api`) for the effect before
re-running — an empty-looking failure may already have applied.
