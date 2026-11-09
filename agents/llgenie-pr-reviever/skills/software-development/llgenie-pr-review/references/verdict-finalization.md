# Verdict finalization: one comment, verification-first write-back, no duplicates

Depends on `references/body-gate-agents-base.md` for the verdict body shape. This file covers *how the verdict and the acceptance write-back get onto the wire without duplicates*.

## 1. A repeated command set re-posts. Verify on-wire before re-running a write.

A batched terminal invocation can be replayed by the runtime: the same `gh pr review --comment` / `gh issue comment` / `gh api -X PATCH` set runs twice and the second pass is not a no-op — GitHub creates a second comment, a second review, a second PATCH. Symptoms: empty or truncated tool output that *looks* like the write failed, followed by a retry that stacked a duplicate.

Rule: after any write that looks failed or produced no visible output, **read the wire instead of re-running**.

```bash
# comments: full list with ids, authors, timestamps
gh api repos/<owner>/<repo>/issues/<n>/comments --paginate \
  --jq '[.[] | {id, user: .user.login, at: .created_at}]'
# formal review submissions (state + head)
gh api repos/<owner>/<repo>/pulls/<n>/reviews \
  --jq '[.[] | {id, state, user: .user.login, at: .submitted_at, head: .commit_id}]'
```

A successful tool call is not a successful task; equally an empty tool output is not a failed task. Only the API read is a fact.

## 2. Exactly one verdict comment; the provenance marker picks the survivor.

Every verdict body carries `(proven: reviewer=<lane> comment=<id> head=<sha> run=<id>)`. When duplicates exist:

1. Read the wire (commands above).
2. Keep the comment whose id equals the `comment=` id in the provenance marker.
3. Delete the others: `gh api -X DELETE repos/<o>/<r>/issues/comments/<id>`.
4. Re-read and confirm the surviving set is exactly one verdict-carrying comment before reporting.

Do not "soften" a duplicate by editing it — delete it, and say in your report which id survived.

## 3. Write the acceptance boxes through the idempotent finalizer, not by hand.

Use the repo's finalizer (`scripts/review_finalize.py finalize`, or the acceptance-writeback seam it wraps) rather than a hand-rolled `gh api -X PATCH` on the issue body. It is verification-first:

- reads the live body, counts `- [x]` boxes and citations, and returns a no-op if the body already carries `criteria-count` ticked boxes each citing the current comment id;
- refuses to PATCH a moved head;
- asserts the read-back (`box count == criteria count`, `cite == comment id`) before printing `landed` — a body that comes back unticked is reported `unconfirmed, re-read the wire`, never `landed`.

```bash
python3 scripts/review_finalize.py finalize \
  --repo <owner>/<repo> --pr <n> --issue <closing-issue> --head <sha> \
  --criteria <k> --proven 1,2,3,...,k \
  --verdict-ref 'reviewer=<lane> comment=<id> head=<sha> run=<id>' \
  --comment-id <id>
```

Head guard, always immediately before the write-back: compare the live PR head to the sha you judged (`gh pr view <n> --json headRefOid`); empty live counts as moved. Never PATCH boxes onto a head you did not measure.

## 3a. A head that moves AFTER the write-back landed needs a re-anchor, not just a re-verify

The finalizer stamps `head=<sha>` into every ticked box. If the PR head moves afterwards (a peer force-push with new content), those citations now point at a superseded sha — the boxes stay ticked but their evidence anchor is stale. Re-measuring each criterion at the new head is only half the job; the other half is **re-running the finalizer at the NEW head** so it re-anchors the `head=` field on every cited box. Confirm the re-anchor on the wire, never from the finalizer's message:

```bash
gh issue view <n> --json body | python3 -c "
import json,sys,re
b=json.load(sys.stdin)['body'].split('## Acceptance criteria',1)[1].split('## ',1)[0]
tick=[l for l in b.splitlines() if l.strip().startswith('- [x]')]
print('ticked', len(tick), 'heads', sorted({m.group(1) for l in tick for m in [re.search(r'head=(\\w+)', l)] if m}))
"
```

Every ticked box must cite the new head; a mixed set (some old, some new) means the PATCH did not cover them all — re-read and re-PATCH, never report it landed.

**`unconfirmed, re-read the wire` from the finalizer is a failsafe, not a failed write.** It fires whenever `ticked-box count != criteria-count` OR `cite != comment id`. When one criterion is deliberately unticked (its fix is a tracked, separate issue), `criteria=k` vs `ticked=k-1` makes "unconfirmed" the *expected* output even though the PATCH landed exactly right. Do not read it as failure and do not re-post; read the wire to confirm the re-anchor (all ticked boxes cite the new head, the unproved one still `- [ ]`) and report the re-anchor with that read-back. A correct write that reports "unconfirmed" because a criterion is honestly unmet is the seam being truthful, not broken.

## 4. Prove idempotency by replaying the finalizer itself.

When the PR's own acceptance criterion is "a replay must be a no-op", the cleanest evidence is a live replay of the finalizer against the already-written body:

- expect exit 0 and a message like `already finalized: … idempotent no-op`;
- expect **no second PATCH** — the closing issue's `updatedAt` must be unchanged (`gh issue view <n> --json updatedAt`);
- expect the head to still equal the judged sha.

Report those three facts (rc, unchanged `updatedAt`, unmoved head) rather than saying "idempotent".

## 5. Two artifacts on the PR: the verdict comment and the consequence note.

The verdict comment states the verdict at the head. The consequence note is a second, short comment on the *implementing* PR recording: what is now ticked (with the provenance pin), the run id held, what CI red remains and why it is by-design, and that merge is the owner's call (this lane never approves/merges/arms). Later readers use it to see what the landing changed without replaying the whole review. Write both, keep both free of duplicates.

## 6. A completion guard asking for a mutation is not satisfied by more reads.

If a check reports "no task-relevant mutation", the remedy is to perform the outstanding mutation (the verdict post, the write-back, the consequence note) and then verify it on the wire — repeated read/verify passes produce no state change and will keep tripping the guard. Do not invent a redundant mutation either: post only artifacts whose absence is real (e.g. a missing consequence note), never a second verdict.
