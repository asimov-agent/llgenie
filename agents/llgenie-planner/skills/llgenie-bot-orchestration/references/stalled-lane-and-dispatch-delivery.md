# Reassigning a frozen lane, and getting the dispatch to land

## A lane that will not start

A lane that freezes on an issue produces the same signature every pass: no branch on the remote, no
claim, no PR, while it acknowledges orders and reports "about to push". Re-sending the same order a
third or fourth time does not move it — the queue is not the constraint.

Procedure:

1. Measure once per pass: `git ls-remote origin "refs/heads/fix/<n>*"` plus `gh pr view <n> --json
   state,headRefOid`. Two consecutive passes with an empty branch list is a frozen lane, not a slow one.
2. Look for a lane that already holds a *verified* copy of the work — a lane whose own comments on the
   issue contain both halves of the diff plus the red-control/passing proofs. A finisher needs the
   diff, not the authorship.
3. Post the reassignment on the issue thread (who is relieved, who takes the finisher role, why) and
   send the relieved lane an explicit "do not touch this issue" line in the same dispatch, so the two
   cannot race onto one vehicle.
4. Give the finisher the mechanical steps only: branch name, rebase onto the freshly fetched `main`
   sha, "one ready-for-review PR closing #<n>", and the two things to report back (pushed sha + PR
   number). Never re-derive the technical content — it already proved it.
5. Do not reassign work whose only copy is an uncommitted worktree (a crashed worker's tree, a
   commit that exists only on that host's clone). Say so instead: that commit is not extractable by
   any other lane, so the constraint is the host, not the dispatch.

A reassignment lands in minutes when the finisher already holds the diff — that is the measurement
that tells you the frozen lane was the problem and the task was never the problem.

## Verifying a finisher PR in one API block

Accept a finisher report only against one block that answers everything at once:

```bash
gh pr view <n> --json state,isDraft,baseRefName,headRefOid,mergeStateStatus,body   # OPEN, non-draft, base main, closes #<issue>
gh pr view <n> --json autoMergeRequest --jq '.autoMergeRequest'                      # armed != "gh pr merge --auto exited 0"
git ls-remote origin refs/heads/<branch>                                            # the sha the lane claims is really pushed
git diff --stat origin/main...origin/<branch>                                       # diff scope == the promised files
git merge-base --is-ancestor origin/main origin/<branch>                            # rebased, not stale
```

Then confirm the promised *behaviour* exists in the pushed blob, not in the lane's description:
`git show origin/<branch>:<path> | grep -B2 '<symbol>'`. A marker/guard the lane says it added is
only real when it is in the tree the remote serves.

## Getting a DM to a peer bot at all

- `status=failed` is a hard non-delivery — the peer never saw it. Retry is correct and idempotent
  when the instruction is "do these steps to this one branch".
- `queued` / "remains pending or its outcome is unknown" is NOT a failure. Retrying one of these
  duplicates the instruction; the gateway retains receipt. Leave it.
- "Durably queued for the live Bot Chat owner" is success — stop there.
- `status=ambiguous` with `error: queue_full` is NOT a failure and NOT a delivery: the peer's inbox is
  saturated. Do not resend in the same pass. Cite the saved `evidence_file` path when reporting and
  put the dispatch on the issue thread instead. Do **not** conclude the lane is stalled or idle: a
  `queue_full` lane is frequently busy on an *earlier* item it received some other way, so measure what
  it actually produced (branch, PR, head sha) before deciding whether it needs forcing at all. When the
  queue later drains, a fresh message with new content (the earlier dispatch never landed, so nothing
  is duplicated) is correct — that is not the resend this rule forbids.
- Two hard failures in a row usually mean the peer's session is mid context-compression and cannot
  accept a turn. Wait in the foreground (`sleep 150; date -u +%H:%M:%SZ`) and retry exactly once;
  that third attempt queues durably. Do not loop retries back-to-back.

When a DM cannot land (`queue_full`) but the work still has an owner, put the dispatch on the issue
itself so ownership is on-record without a resend: `gh issue comment <n> --body "<claim + ordering +
brief>"`. Cite the DM evidence_file in that comment. A dispatch that exists only in a failed DM does
not exist for the next reader.

## A report that arrives out of dispatch order

A lane that finishes the *second* item on your line-up while the first shows no branch and no start
comment is the predictable consequence of an undelivered dispatch, not of scope invention. Reconcile
before reacting:

1. Check the earlier item for evidence of a race: `git ls-remote origin "refs/heads/*<n>*"` and the
   issue timeline. No branch and no claim from any lane ⇒ no two-vehicle race; the deviation is
   order-only.
2. Verify the delivered work on its own merits (see `verifying-lane-claims.md`). Scope-faithful work on
   the second item means the lane is functional — the failure was delivery, not the lane.
3. Accept it, and re-push the earlier item *inside* the same follow-up message that sends the gate fix
   back to the delivered PR: one DM, two assignments, explicit order. Never open a second vehicle for
   the delivered item and never re-assign the earlier item to another lane that would then race.
4. Record the reorder on the issue thread so the next reader sees why the line-up changed.

## A dispatched lane that is really a second lane on one vehicle

An orchestration tick can dispatch lane B to "fix PR #n" from a stale snapshot while lane A already owns
that PR and has moved its head. Read the PR state *before* the lane B dispatch lands: `gh pr view #n
--json headRefOid` + `gh worktree list` — if the head the dispatch cites differs from the live one, the
premise is from an earlier pass. Verify wheel ownership before asking B to touch it; the worktree path a
kanban task names may be lane A's own tree (its HEAD is lane A's head sha). Halt lane B on-record with the
live head, shelf the task as superseded, and post the single-owner stand-down on the PR so lane A's claim
stays visible. Do not send two lanes at one branch — the second push overwrites the live head.

## Check a lane's WHOLE vehicle load before gifting it unowned work

"Unowned issue has no open PR" is not the same as "this lane is free." The one-vehicle rule has a blind
spot exactly at dispatch: an issue may be unowned (no open PR for IT) while the lane you are about to gift
it to already holds a DIFFERENT open PR. Two same-class misfires in one pass: I dispatched #1097 (engine
versioning) to llgenie-engine-improver while it held live vehicle #936/#1075 (`feat/ollama-source-build`,
`bot-claim:` on #936), and dispatched #1173 (unit-ceiling pipeline fix) to llgenie-ci-pipelines-maintainer
while it held #1164 (its own skill-tree versioning, branch `fix/1060-ci-pipelines-skill-tree`). Both had to
be stood down and reordered. The check that catches it: before assigning unowned issue X to lane L, run
`gh api repos/<o>/<r>/issues/X/timeline` for X's open PRs (one-vehicle on X) AND sweep X's sibling issues for
L — the lane's own versioning vehicles live on issues like #1060/#1097/#1164 (agents/<lane>/ tree mirrors)
and sit OPEN for long stretches. Canonical test: `gh pr list --author "" --head <lane-branch>` is NOT enough;
the lane holds what its *issue* claims. When L is busy, route X to the general implementer's queue instead,
or reorder X BEHIND L's active vehicle on the same lane and say the ordering plainly. Do not silently load a
second vehicle onto the lane's plate.
- **The lane's own versioning PR may ALREADY exist quietly.** Before routing an own-lane profile-versioning issue
(SOUL/SKILL mirror per #791/#919) to the implementer, check `gh pr view <issue>` and sweep
`gh pr list --head 'fix/<issue>-*'`: the owning lane frequently opens its `fix/<issue>-sync-live` PR silently
(PR #1190 for #1097 was already OPEN before I re-routed #1097 to the implementer — a two-vehicle misfire I had to
unwind). Own-lane versioning belongs to the owning lane by default; the implementer gets it only when that lane is
truly idle with no vehicle. If the lane already holds the PR, the decision is reorder-behind-its-active-vehicle or
close-and-migrate — never two vehicles on one issue.
- **A pre-existing auto-merge arm is not "somebody re-armed it."** When `autoMergeRequest.enabledAt` predates the
session, the lane reading it is observing, not placing; do not demand a disarm, report the arm date as read, and
leave arm/disarm to owner/planner. Do not push through a live run at the head to "help" it.
- **An agents-tree SOUL/SKILL versioning PR needs the #1123 note+fragment BEFORE dispatch.** A PR that changes
`agents/<lane>/.../SKILL.md` or a Makefile row (per #791/#919) REDS `scope → make check-docs` unless the same branch
carries the paired `agent-wiki/<stem>.md` note AND its `docs/changes.d/<stem>.md` row — the `change->note` gate
fires with "but adds no agent-wiki/<stem>.md note — a behavioural change owes a note (and its docs/changes.d row);
see issue #1123". This bit twice in one session (#1093 and #1164, both freshly green-bound then red on scope at
head). Pre-empt it in the dispatch: tell the lane "the +N files this agents-tree change touches each owe an
`agent-wiki/<stem>.md` note + `docs/changes.d/<stem>.md` row; run `make docs-report` to name every missing stem,
add them on its own branch, and do not arm until scope+guard+unit are all green at the head." A guard-red fix or a
rebase does NOT cure it — base moves and label/linked-issue fixes never add a note to the branch. This is a
per-file, on-branch, owning-lane duty, so route it to the branch owner, never to the rebase lane.

## Guard reds read authoritative `gh pr checks`, not raw check-runs

At a head, `commits/<sha>/check-runs` returns EVERY run including stale earlier attempts; `gh pr checks`
honours latest-attempt-per-name and is the binding verdict. A raw list can show `guard [failure]` from 11:31Z
alongside two green guards while the live verdict (gh pr checks) also reports `guard bucket=fail`; the raw
failure is REAL if the authoritative read agrees. Do not flip-flop on which — measure both, then trust the
`gh pr checks` verdict, and always bind the claim to the head sha you actually read. Also: a guard leg with
NO output body (empty summary/text/title) is a label/linked-issue check, NOT a rebase-fixable red — a base
move never touches the linked-issue; that is the do-not-merge-with-no-remedy leg (#948). Report it as the
owning lane's remedy, never as "rebase and see".

## Issue number vs PR number — the right gh verb

A dispatch cites `#<n>` that may be an ISSUE or a PR; they are separate gh subcommands and mixing
them fails silently or confusingly:

- `gh pr comment <n>` / `gh pr view <n>` on an ISSUE number → GraphQL `Could not resolve to a
  PullRequest with the number of N`. That error is the diagnostic that `<n>` is an issue, not a PR —
  switch to `gh issue view` / `gh issue comment`.
- A "missing PR" that appears for a lane's active issue is usually just the issue number: the lane's
  real vehicle is a branch whose PR has a different number (find it with `gh pr list --head <branch>`
  or `gh pr list --search <keyword>`), not a vanished PR.
- Post dispatch/claim comments with `gh issue comment`; post review/verdict comments with
  `gh pr comment`. Never promote a dispatch meant for the issue onto a PR, and vice versa.

## Exact-match census pins vs. the PR that changes the set

When a pin asserts `set(actual) == EXPECTED` over a registry (network markers, roster, manifest), a
PR that legitimately adds entries to that set reds the pin — by design. The fix belongs in the *same
branch and vehicle*: extend the expected census with the names the PR added, push to the existing
branch, re-read the arm. A second PR for the census is the two-vehicle mistake.

Read the assertion diff before triaging: `actual - expected` naming exactly the entries the PR
introduced means the PR is correct and the census is stale. Entries in `expected - actual` mean the
lane dropped coverage it did not intend to drop — that one is a real defect.
