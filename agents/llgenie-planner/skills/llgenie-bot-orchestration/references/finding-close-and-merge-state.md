# Finding closure and merge-state read-back

> See-also: `pr-closing-gate.md` (the gate that demands an adjacent `closes`). This file is
> about WHEN a `closes` is legitimate, and how to read a PR's real state.

## A record/triage PR must not `closes` a finding whose acceptance needs landed code

A docs-only vehicle (a change-note row + wiki fragment, a triage record) that carries
`closes #N` will auto-close a finding whose own acceptance criteria demand a real code
fix — the issue then reads CLOSED on the board while the fix does not exist. Caught
twice in one evening (#1596→#1595, #1599→#1598).

- Prevent before merge: read the PR's `closingIssuesReferences`
  (`gh pr view <n> --json closingIssuesReferences`) against the diff
  (`gh pr view <n> --json files,additions,deletions`). Docs-only diff + a `closes` on a
  finding with unmet acceptance = dispatch the author to DROP the close-claim (the record
  stays a disposition record; the *fix* PR carries the close).
- If it already merged: `gh issue reopen <n>` (there is no `--state` on `gh issue edit`),
  then comment the board record. Verify `state=OPEN, stateReason=REOPENED` off the API
  afterwards — the reopen flag is a dedicated command, not an edit field.
- The correct closure shape is: finding issue OPEN → FIX PR carries `closes #finding`.
  Closing a finding on its fix PR (verified diff + AC evidence) is right; closing it on
  a record PR is the premature-close defect.

## An OPEN issue that already landed: verify ACs on main, then close COMPLETED citing the sha

A lane that measures `origin/main` before writing can find its queued issue already
satisfied by an earlier PR and correctly refuse to re-implement (duplicate-PR trap). Do
not close on the lane's say-so — verify first, then let the lane carry the close with the
citation:

1. Read the issue's own acceptance criteria (`gh issue view <n> --json body`).
2. Measure each AC against `origin/main`, not the primary clone:
   `gh api repos/<o>/<r>/contents/<path>?ref=<main-sha> --jq .content | base64 -d` and
   `git -C <repo> show <sha>:<path>`.
3. Confirm the cited landing commit is on main: `git merge-base --is-ancestor <sha> origin/main`
   and `git show -s --format='%h %s' <sha>` — the subject should name the issue's own asks.
4. Dispatch the owning lane to comment + close COMPLETED citing that sha and the AC evidence,
   so a stale-OPEN hole is not re-read as work by issue-bot or the next queue ask.

## A fix PR's `closes` closes the ISSUE — it does not satisfy the finding's EVIDENCE gate

A finding whose acceptance box is a **run that proves the fix** (e.g. a security finding: "the next scan
closes this issue with the run that cleared it") will be auto-closed at the FIX PR's merge by its
`closes #N`, with every acceptance box still UNCHECKED. Mechanically closed; substantively the evidence
gate never fired. Do not conflate the two, and do not report either "silently cleared" or "properly
closed" before measuring.

Verify in this order (each against the API, not a lane's summary):

1. **Did the fix genuinely land on live main?** Read the file, not the PR diff:
   `gh api repos/<o>/<r>/contents/<path>?ref=<main-sha> --jq .content | base64 -d | grep -nE '<marker>'`.
   Marker present on main = the finding is genuinely gone from source.
2. **How did it close?** `gh api repos/<o>/<r>/issues/<n>/timeline?per_page=100 --jq '[.[]|select(.event=="closed" or .event=="referenced")|{e:.event,at:.created_at,actor:(.actor.login//.user.login)}]'`.
   A close 2–3 s after the merge, actor = the merger, is a **merge-reference close**; a close minutes/hours
   later by a bot workflow is the evidence gate.
3. **Is the cited "clearing" run actually a clearing run?** `gh api repos/<o>/<r>/actions/runs/<id> --jq
   '{head:.head_sha,conclusion}'` — if its head predates the fix's merge head, it is the run that
   **REPORTED** the finding (cited in the issue's "Scan run" field), not the one that cleared it.
4. **Does a post-fix confirming run exist at all?** Filter the scanner workflow's runs by the fixed
   main tip; an empty result means the evidence gate has not fired yet.

Decision:

- **Fix present on main ⇒ do NOT reopen.** Reopening a source-fixed finding is ritual and churns the
  board. Instead post the adjudication on the issue (closed-by-merge-reference, boxes pending run
  evidence, the file + sha proving the fix), route the tick to the owning lane with the exact condition
  (tick the boxes ONLY on a genuine COMPLETED clearing run, naming run id + head sha), and file the
  process reflex — a bot merge-closing a finding whose acceptance box is run-evidence should refuse
  until the evidence exists.
- **Fix ABSENT on main ⇒ reopen** (`gh issue reopen <n>`), then re-verify `state=OPEN,stateReason=REOPENED`:
  the issue was closed on a false premise.
- Never tick the boxes yourself off the reporting run — that turns an evidence gate into a formality
  and is exactly the bypass being audited.

## A merge-reference close can cite a commit ORTHOGONAL to the named defect

The step above asks "did the fix land on main?". It is not enough: a `completed` close can
follow a merge whose commit changed a *different aspect* of the same file. Measured case: a
timeout-wall finding was closed `completed` by a PR whose diff added a build-cache write-back
flag (`--cache-to ... mode=max` when an env guard is set) to the same `engine-build.yml` —
real work, but the `timeout-minutes` line it named as the defect was untouched (still the old
value on `origin/main`). The close was mechanically attributable to that file, substantively
never to the defect.

So before treating a merged `closes` as remedy-done, **diff the closing commit against the
issue's named defect, not against its filename**:

```bash
git show <closing-commit> -- <path> | grep -nE '^[+-]' | grep -iE '<the defect marker>'   # the exact line, or nothing
gh api repos/<o>/<r>/contents/<path>?ref=main --jq .content | base64 -d | grep -nE '<defect marker>'  # what main actually has
```

An empty diff on the defect marker + the marker still present on main = the close is not
remedy-done (this is the same reopen bar as "fix ABSENT on main" below) — but disposition it
respectfully when the issue already carries `do-not-merge` or the owner/reviewer settled its
remedy chain: record the evidence, let the owner decide the reopen, do not force it.

## CLOSED is not MERGED — a premise built on "closed in #P" can be a false premise

A PR that never merged — and its branch — can still be cited as "owner closed that in #P",
by a lane commit, a SKILL note, or a review comment. That reads as "resolved" and everyone
downstream assumes the change is on `main`; it is not.

```bash
gh pr view <n> --repo <o>/<r> --json state,mergedAt,mergeCommit \
  --jq '{state,mergedAt,merged:.mergeCommit.oid}'
```

- `state=CLOSED, mergedAt=null, mergeCommit=null` → **closed un-merged**: the change is NOT on
  `main`. Verify the named line on `origin/main` before repeating any "handled" claim.
- Only `state=MERGED` with a non-null `mergeCommit` and `git merge-base --is-ancestor
  <mergeCommit> origin/main` → YES means the change landed.

When a lane's note or commit message rests on "closed in #P", and #P is closed-un-merged, the
premise is false: correct it on-record (name the PR state + the still-live line on main) and DM
the author, rather than letting the wrong "resolved" propagate. Closed means a decision was
made about the PR; it says nothing about whether the change reached the default branch.

## Merge state: read BOTH surfaces (the #1600/#964 trap)

A lone REST read lies about the dangerous direction on a review-blocked PR.

- Read REST `auto_merge.enabled_at` AND GraphQL `autoMergeRequest { enabledAt ... }`.
  `armed` if EITHER is non-null; `none` only when BOTH are null. A `gh pr merge <n> --auto`
  can exit 0, REST `enabled_at` read NULL the same second, while GraphQL `enabledAt` is SET
  and the PR merges behind the review gate (#1599: armed 14:27:27Z, merged 14:29:30Z).
- Dis-arm is `gh pr merge <n> --disable-auto` (NOT `--cancel`); read both surfaces back null.
- Before quoting any merge state, re-read `state,merged,mergedBy,mergedAt,merge_commit` — a
  lane narrating `state=OPEN` on a merged PR, or `enabled_at=NULL` off a REST-only read, is
  a stale/false-negative claim, not evidence. The API is the evidence; a repeated contrary
  claim is not.
- `gh issue comment` has no `--jq`; `gh pr view --json statusCheckRollup --jq` indexes
  `.statusCheckRollup[]` directly (not `.[0]`).
