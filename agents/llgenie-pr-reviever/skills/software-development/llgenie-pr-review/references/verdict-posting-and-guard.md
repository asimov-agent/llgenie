# Posting the verdict and satisfying the session guard

## The guard firing "no task-relevant mutation" after an external write

A verdict posted with `gh pr comment` / `gh pr review` / `gh issue comment` is an **external**
write. It lands on GitHub and is verified there, but it is **not** a session-observable mutation —
the session-integrity guard does not see it and will keep reporting "no task-relevant mutation was
attempted" even though the deliverable exists.

Do **not** respond by:

- **Re-posting the verdict.** A duplicate verdict comment is churn, and on a review it reads as two
  conflicting frames. The first post already landed; re-sending does not change the wire.
- **Reaching for an out-of-lane code edit.** A reviewer never implements; editing code to appease a
  heuristic is exactly the failure the lane exists to prevent (`#1088`).

Do respond by making a mutation that is **both in-lane and observable in the session**:

1. **Record the durable lesson from the review in this skill** (`skill_manage` patch / reference
   file). A completed review produced findings; encoding them is a real, in-lane, observable change.
2. **Post the same finding on the OTHER artifact the dispatch permits.** A dispatch worded "a verdict
   on #<pr> **and/or** #<issue>" explicitly authorises the issue-side comment — and the issue is
   where the owner/implementer will actually act on a defect a PR cannot fix on its own (an issue
   body in the wrong heading shape, a criterion the gate cannot read). The "and/or" is the coupling
   contract that keeps a verdict reachable: record it on the PR *or* the issue, whichever the fixer
   reads.

## A COMMENTED review does not clear `REVIEW_REQUIRED` — the bot-verdict marker + auto-merge's other identity does

`gh pr review -a` is refused on any PR this lane's token authored: `422 "Review Can not approve your
own pull request"`. Since the fleet pushes with one owner token, **the author of most bot PRs IS the
token account**, so `mergeStateStatus: BLOCKED` + `reviewDecision: REVIEW_REQUIRED` can never leave
`REVIEW_REQUIRED` by an approval this lane posts. A posted COMMENTED review is a record, not the
merge clearance.

The designed path, and the one to verify rather than fight:

- `review-verdict` (a `pull_request_review` workflow) records a review whose state is `approved` or
  `changes_requested`; a `commented` review makes it skip — by design. So a comment-only lane gets no
  marker from that workflow.
- `scripts/bot_verdict.py` owns the marker `<!-- bot-verdict: head=<full sha> run=<run id>
  verdict=<approve|changes> reviewer=<login> -->`, trusted only from `TRUSTED_VERDICT_AUTHORS`, and
  the `reviewer=` must equal the comment's author.
- `scripts/auto_merge.py` reads that marker; when the PR is `BLOCKED` **only** on the review, a
  verdict at the exact `headRefOid` clears the block, and the job then **approves as the identity
  that is not the author** and merges.

So the correct lane action is: post the evidence-bearing review + the acceptance write-back, then read
the state instead of asserting it:

```bash
make -s bot-verdict-read REPO=<owner/repo> PR=<n>     # what the merge gate would see at the head
gh api repos/<R>/pulls/<n> --jq '{state,merged,merge_commit_sha,mergeable_state,reviewDecision}'
gh api repos/<R>/pulls/<n>/reviews --jq '.[]|{state,user:.user.login,commit:.commit_id[0:8]}'
```

`no trusted verdict for this head` + a green chain means the marker/auto-merge sweep has not run yet
(it fires on `workflow_run` completion and on the odd-minute schedule) — wait for the sweep, do not
manufacture an approval. An `APPROVED by github-actions[bot]` row is the auto-merge job acting under
the other identity: that is the repo's mechanism working, not a stranger approving. Never merge, never
arm, and never post a bot-verdict `approve` for a PR whose criteria you have not proven at that head.

## Guard pressure is not a licence to self-select an unreviewed PR off the board

When the guard keeps firing on a genuine no-mutation turn (runtime bind held, nothing fabricable),
an **open PR with zero reviews** sitting on the board looks exactly like "owed work" and tempts a
sweep — pick the newest unreviewed PR and review it to manufacture a session-observable change.
Do **not**. This lane reviews what the planner delegates (#1010/#1015); it does not self-select off
the board while the fleet dispatches. An unreviewed PR is the *dispatcher's* to assign, to whatever
lane it belongs — a reactive verdict delivered only to quiet a heuristic is both out-of-routing and
a verdict posted before the lane that owns the change was asked for it. The honest artifact on a
no-mutation turn is the durable record (consolidated board state, a skill lesson), never a
self-assigned review. Name the unreviewed PR in your status to the planner as a *candidate for
delegation* — do not act on it yourself.

## Verify every external write by read-back

A zero-exit `gh comment` is not proof the comment landed — verify the `id` and `created_at`:

```bash
gh api "repos/<owner>/<repo>/issues/<n>/comments" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); \
      print([(c["id"],c["created_at"]) for c in d if "<unique phrase from the body>" in c["body"]])'
```

Match the new id/createdAt before you report the verdict as posted. `gh pr comment <n>` prints the
new comment URL — read it back rather than trusting the exit code.

## SKILL.md was at the size limit

The `llgenie-pr-review` SKILL.md sits hard against the 100,000-character cap, so a growing body of
lessons cannot be appended there. New durable lessons belong in a **topical** `references/*.md`
file (this one), not appended to SKILL.md — a `skill_manage` patch that grows SKILL.md will be
refused once it exceeds the cap. When SKILL.md needs to shrink, move a settled section wholesale
into a `references/` file and leave a one-line pointer, rather than trimming individual lessons.
