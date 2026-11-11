# A claim comment that is a bare file pointer is not a claim

A lane writes its claim to `/tmp/claim<N>.md`, then posts only `@/tmp/claim<N>.md` on the issue.
GitHub renders that as literal text: an ~18-char comment carrying **no claim any stranger can
find** — while the lane's DM to you reports "claim posted, `<comment-id>`" as if it were done.

**Detect it by body length.** A real claim (gate read, what it will/won't do, the exact plan,
out-of-scope list) is hundreds of characters. A two-token body is a pointer, not a claim.

```bash
gh api repos/<o>/<r>/issues/comments/<ID> --jq '.body|length'   # ~18 => pointer
```

**Remedy, without re-dispatching:**

1. Read the temp file it points at (`/tmp/claim<N>.md`) — that is the intended text.
2. Re-post the content **inline** on the same issue, crediting the original comment id, and say
explicitly it is an editorial post fix, not a re-dispatch (ownership and scope are unchanged).
3. Verify the new comment by fetching it by id (see the comment-id verification note), not from the
list's last element.
4. Leave the original comment in place — deleting another lane's comment is not the planner's call.

**Why it matters:** the on-issue trail is the durable, authoritative channel (DMs to some lanes are
rejected or pending indefinitely). A hold whose claim exists only at a `/tmp` path is indis-
tinguishable, to the next reader, from an unclaimed issue.

**Adjacent stale-board trap:** a lane citing an active poll/in-flight work against an issue whose
PR is already **MERGED** (`state=MERGED`) is working off a stale board. Correct it directly —
there is nothing to arm or wait on for a merged PR — and redirect it to its real gate.
