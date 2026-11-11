# Transport acks are not a turn-ender; work the board in batches

Read first when a pass would otherwise end in "No action", and whenever a board has more open obligations than one comment can clear.

## The failure mode
When you DM a lane (`message_agent`) the tool returns `{status: queued, delivery_id: …}`. Later a background process reports `"pending / delivery pending or outcome unknown / do-not-resend; receipt retained"`. These are **transport receipts**, not lane replies: no lane content, no board state, no claim of progress.

Stalling on them — pass after pass of "No action, receipt retained, not new state" — is idleness. The board did not change because you did nothing; you did nothing because you were reading receipts. Repeated identical acks (several lanes, or several distinct delivery ids for one lane) are still just receipts; uniformity is not evidence of a stuck system, it is evidence you have not dispatched work.

Rule: a queued dispatch is **not** a landed task, but a receipt is **not** a reason to stop either. Record the delivery id, move on, keep working the board.

## What a pass must actually do
Every wake ends with at least one of: a dispatch, a close with evidence, or a written reason nothing *could* move. "A receipt came back" is none of those. Per wake:

1. **Inventory from the API, not memory**: `gh pr list --state open --json number,headRefName,mergeable_state,isDraft`; open issues with no live vehicle; tracker issues whose gate is red.
2. **Work several obligations in ONE turn, in parallel** — roughly a dozen at a time. Independent mutations batch: post record A, post record B, DM lane C in one assistant turn. Do not serialize one comment per turn.
3. **Verify each mutation by read-back** before claiming it landed: `gh api repos/OWNER/REPO/issues/comments/<id> --jq '.id,.issue_url'`. A `posted=<id>` echo is the POST succeeding, not the task.

## Posting comments reliably (jq / shell pitfalls)
- **Never build a comment body with inline jq or shell interpolation.** `--jq '" #"+(.number|tostring)'` and `$n` inside single quotes break silently or emit garbage; an empty `--jq` result looks like a clean run. Write the body to a file and post with `-F body=@/tmp/file.md`, then read the returned `.id` back.
- **Read fields one at a time**, not in one big inline jq: `gh issue view N --json state --jq '.state'`, then `--json title --jq '.title'`, then `--json comments --jq '.comments[-1] | {user: .user.login, body: .body[0:160]}'`.
- Put multi-issue loops in a small shell script written to a file and run it, rather than one giant one-liner.

## Post-merge attribution
After a PR merges, re-read `main` at the merge tip. If a gate is red there, decide **whose defect it is before filing anything new**:
- Verify the merged PR's own acceptance criteria **on `main`** (`git show origin/main:<path>`; grep for the symbol), not on the PR branch.
- If the red reproduces a **pre-existing open issue's class** (same truncation/log/failure signature at the merge tip), post a fresh reproduction comment on that OPEN issue and re-demand its vehicle. Do **not** file a duplicate, and do **not** reopen the merged PR — its diff is now `main`'s.
- File a new issue only when the red is genuinely new and cannot be attributed to an open umbrella.

## Duplicate findings
Two open issues with byte-identical bodies (same scanner rule, same file:line, same region) are one finding filed twice. Name the twin, keep the labelled one canonical, cut ONE vehicle. Do not let the lane produce two fix PRs.

## Stale-base PRs
A PR whose `base.sha` is behind the live `main` after an intervening merge shows failures that are not its own (e.g. a main-wide truncation gate reds every branch's `ci-verdict`). Order a rebase onto the live main tip FIRST, then re-read CI at the NEW head before diagnosing content failures — a stale-head verdict is not a diagnosis.
