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

## Never cite an id you did not resolve — a fabricated number is a false dependency

An issue/PR number invented inside a dispatch (a "next one" estimated from the sequence, a stacking hint
like "rebase onto #<n> if it lands first") is worse than no reference: the lane reads it as a real
dependency and either waits on a vehicle that does not exist or reports against it. Before any comment or
DM names a number, resolve it:

```bash
gh pr view <n>    -R <o>/<r> --json number,state    # 404 = no such PR
gh issue view <n> -R <o>/<r> --json number,state    # 404 = no such issue
```

Quote only numbers you resolved this pass, and only numbers you actually read from the API — never a
number recalled from an earlier window, and never one inferred from "the filer will pick the next id".
Conditional advice ("if X lands first") is only usable when X is a live, resolved vehicle; otherwise drop
the conditional entirely rather than leaving a placeholder-shaped number in its place.

The correction is immediate and dual: post it on the vehicle's own thread so the record is durable
(`gh issue comment <n>` naming the fabricated id, the 404 that proves it, and the clause to disregard),
then send the lane ONE corrected dispatch. Do not leave the correction only in the DM — the board is
what the next reader sees — and do not silently let the lane act on the invented dependency.

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

## A DM that lands successfully is still not a board vehicle

A `status=queued` / "durably queued" dispatch is delivery, not discoverability: nothing on the board says
the lane owns that work, so the next reader (or a completion gate) sees an idle lane and an unowned task.
This bites hardest on the standing *own-domain audit* dispatches, which have no issue of their own to
hang a `bot-claim:` on — the audit becomes invisible and unmeasurable.

Rule: after any dispatch that assigns work with no existing open issue, file the tracking issue in the
six-section shape, label it with labels that actually exist, and post the `bot-claim:` for the target
lane naming the scopes and the exact "done" (refined six-section findings through the normal queue, or
`re-audited at <sha>, no findings` closed on that issue). Opening the vehicle is the planner's work;
closing it is the lane's.

Two mechanics that silently fail here:
- `gh issue create --label X` with a non-existent label creates nothing usable — validate first:
  `gh label list --json name --jq '.[].name'`. Guessed labels (`continuous-improvement`) are the usual
  offender; existing stand-ins are `documentation`, `enhancement`, `initiative`, `agent:implement`.
- Read back (`gh issue view <n> --json number,state,labels` and
  `.../issues/<n>/comments --jq '.[-1].body'`) before calling it landed.

## Verifying a branchless `workflow_dispatch` lane actually picked up

Some lanes work through a workflow (`engine-build` / `push-engine`) rather than a branch, so "no branch,
no PR" proves nothing. Measure the workflow's own run list and look for a NEW run at the correct head:

```bash
gh workflow list --all --json name,id --jq '.[]|select(.name|contains("engine"))'   # find the workflow id
gh api "repos/<o>/<r>/actions/workflows/<id>/runs?per_page=2" \
  --jq '.workflow_runs[]|"id=\(.id) run=\(.run_number) head=\(.head_sha[0:8]) \(.status)/\(.conclusion // "na") \(.created_at)"'
```

- The fresh run's `head_sha` must be the sha you ruled on. A run at a superseded head that later reads
  `cancelled` is the stale dispatch dying, not the lane working.
- Track the pair: stale run `cancelled` at the old head + new run `pending` at the correct head is the
  strongest evidence a reroute took effect — quote both ids, never a summary of intent.
- `gh run view <run_number>` 404s: the run **number** is not the run **id**. Use the id from the runs
  list, or `gh run list --workflow <name>`, which resolves it for you.
- Branch-based lanes: measure pickup with the branches API too (`repos/<o>/<r>/branches?per_page=100 |
  grep <issue>`) — a dispatched issue that has no branch is not started, however many DMs were queued.

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

## A lane ships before your scope amendment lands — verify by residual scan, then one corrective vehicle

A mid-run scope amendment ("add this 13th file to the fold set") loses a race with a lane that has
already committed: it reports the original scope as DONE with the extra item still outstanding and
cites your *superseded* bound as the reason. Do not reopen the merged PR (its diff is now `main`) and
do not treat the report as false — it is scope-faithful to the pre-amendment brief.

1. **Prove the delivered part fully landed.** `git cat-file blob origin/main:<path> | sha256sum` per
   file against the live source; a per-file OK/DIFF list settles the 12-of-13 question in one block.
2. **Residual-scan for what is left**, don't trust the lane's own list: walk every file in the
   references dir on `main`, compare to the live dir, and also `comm` live-vs-tree for live-only
   files. Output "present-but-diff count=N" + any live-only names. This is the evidence the next
   reader and the corrective dispatch both need.
3. **File one follow-up issue** naming the missed item, the measured live-vs-tree shas/sizes, and the
   root cause (amendment landed after commit). One PR, one file, `closes #<new>`. Never a second
   vehicle for the already-merged part.
4. **State the process correction on-record and in the dispatch**: when the orchestrator amends scope,
   the lane confirms receipt/action on the live issue before holding an earlier "don't touch" bound.
5. **A planner-owned references dir is an ACTIVE lane** — live copies grow mid-run, so every fold
   re-measures live immediately before commit and folds whatever live says at that moment (the
   aggregate sha moving between branch and merge is normal, not an error).
6. Expect docs-class merges to land before their own main-CI verdict: a main run `in_progress` at the
   merge tip is pending, not green — carry it to the next pass rather than quoting it as passed.
7. **A file in the fold's changed-list ≠ folded to current live.** A fold that includes a file can still
   carry a *stale* snapshot of it: the live profile was edited after the fold captured its copy but
   before the merge, so the diff reads `+N -0` while live is longer than the merged tree. Symptom: the
   post-merge gate at the merged sha still reports that lane's file `live-longer` (tree size < live size,
   lines the tree lacks). Do not trust "it's in the PR's file set" or the lane's DONE report — measure the
   merged blob against live at the merge-commit sha: `git show <merge-sha>:<path> | wc -c` vs the live
   file's `wc -c`; a tree size short of live means a pre-edit snapshot landed. File a NEW follow-up issue
   naming the merged PR + its merge sha + the failing gate + the exact sizes, delegate to the owning lane
   (never reopen the merged PR — its diff is now `main`), and require the corrective fold to re-measure
   live **immediately before commit** so it cannot reproduce the same race.

## A dispatched lane that is really a second lane on one vehicle

An orchestration tick can dispatch lane B to "fix PR #n" from a stale snapshot while lane A already owns
that PR and has moved its head. Read the PR state *before* the lane B dispatch lands: `gh pr view #n
--json headRefOid` + `gh worktree list` — if the head the dispatch cites differs from the live one, the
premise is from an earlier pass. Verify wheel ownership before asking B to touch it; the worktree path a
kanban task names may be lane A's own tree (its HEAD is lane A's head sha). Halt lane B on-record with the
live head, shelf the task as superseded, and post the single-owner stand-down on the PR so lane A's claim
stays visible. Do not send two lanes at one branch — the second push overwrites the live head.

## A lane refutes a dispatch you never made — queued DMs replay earlier windows

A lane replying "your #N dispatch was grounded on a false premise / main is not `<sha>` / that issue is
already closed" may be answering an instruction that is **not on your live board**: a DM queued in an
earlier context window replays after compaction, so the lane reacts to the old text while your current
line-up says something else. Signature: the lane states a premise, sha or issue you do not hold open
right now, and its refutation is *internally correct* against that stale premise.

Do not re-argue from memory and do not re-dispatch to "correct" it — that starts ping-pong. Instead:

1. Grep your own pass record for the cited id. If you never dispatched it this session, it was a stale
   queued message, not a live instruction.
2. Measure the facts the lane asserts (main tip, PR state, issue state) from the API. Confirm the
   refutation is right *about the stale premise* — it usually is.
3. Send ONE reconciliation: "that premise is from a queued message from an earlier window, not my live
   board; here is the live state." Name the live sha/issue state so the record is unambiguous.
4. Stop. When the lane replies "agreed, no disagreement remains," do not answer again — a further reply
   is the duplicate-delivery mistake the queue rule forbids, now on the receiving side.

Also carry a lane's declared authority boundary as a fact, not a debate: e.g. the ci-pipelines lane does
not rebase PRs (owner instruction) — a rebase need routes to the rebase lane, so a dispatch telling it to
rebase its own PR is wrong on its face and the refusal is correct.

## A fast-merging owner makes every lane's quoted base stale within minutes

The owner merges the sync/copy cohort in streaks: five merges in one hour moved `main`
`1db367a2 → 0c842d24 → e886e05c → 92e03503 → 8b8a6c39 → 543466ca`. Every lane that reported a
base/head in that window was reporting a base already outrun — the implementer, the architect, the
tester and the engine lane each measured against a tip two-to-five merges behind. Consequences to
watch for on every pass:

1. **Never quote a base you did not fetch this minute.** `git fetch -q origin main` then compare the
   PR's `base.sha` against `git rev-parse origin/main`. `base.sha` on the PR object is the fork point,
   not the current tip — a PR can read `base=92e03503` while main is `543466ca`.
2. **A lane saying "waiting only on CI" on a DIRTY PR is the #964 trap.** `mergeable=false,
   mergeable_state=dirty` means that head will never get green and never land; no amount of CI on it
   helps. The remedy is a rebase onto current `origin/main` by the branch owner (fix-PR owners rebase
   their own branches; the rebase lane only for cross-lane conflicts), then re-run CI, then arm only
   on a mergeable+green rebased head with a non-null REST `enabled_at`.
3. **Re-point the rebase target when main moves under you.** A rebase lane given `92e03503` finishes
   onto a base that `543466ca` has already superseded — tell it to fetch fresh at its own turn and
   rebase onto whatever `origin/main` is at that moment, reporting that sha, and expect to repeat
   this while the owner's streak continues.
4. **A lane's head sha in a DM is often an intermediate ancestor.** A lane repeatedly quoted
   `c7446d6f` as its head when the real PR head was `598ca0ce`; verify with
   `gh pr view <n> --json headRefOid` and bind every measurement to that sha.

## A lane looping identical false status reports — escalate out of the loop, don't reply

One lane (the implementer) sent ~16 near-identical status DMs across a gateway glitch, each asserting
the SAME false state at a dead head (`7b00cc33` / "MERGEABLE / 13-14 green, unit in_progress") that the
API contradicted on every axis (`mergeable=false, ms=dirty`, the unit run a completed FAILURE, the head
long superseded). Recognition and handling:

1. **Measure once, post the truth on-record**, then state the ignore-rule explicitly in your next
   message: "a further report quoting `<dead-sha>` / zero reds will be ignored as a false report."
2. **Then hold silence.** A message of exactly that shape gets no reply — replying restarts the loop.
   Do not re-litigate; the on-record issue comment (`6550870908`) is the truth the reviewer reads.
3. **Do not let "watchdog armed" fiction become a hazard.** A loop-claiming lane often says it will
   arm auto-merge "the moment green AT head" — at a dead head that arm would be a #964 trap. Send ONE
   stop-acting instruction to the lane and a coordination note to whoever owns the real head.
4. **Keep working the real signal** (branch motion, CI at the true head, the owner lane's action)
   while ignoring the noise stream; the lane's "going quiet now" is a promise, not a state.

## A lane looping CORRECT settled reports — one explicit release breaks it, then silence

The mirror of the false-report loop: a lane re-confirms the SAME *true* state 6-8 times
("#1225 head `ff4b597d`, mergeable/blocked, merge-tree clean, per-#1015 hold, nothing owed"). It is
not wrong — it is trapped resolving STALE dispatch re-deliveries queued in an earlier window that
keep asking it to "rebase onto `<old-sha>`" / "head is `af92e048`", premises it already superseded.
Each replay triggers a fresh correct refutation, so the loop feeds itself.

Handling differs from the false-report case (where you escalate once then go silent with NO reply):
here the lane's last message is usually a legitimate boundary question ("do you want an owner-level
re-anchor override?"). Answer it ONCE, explicitly, to break the loop:

1. State plainly that no new order exists: the dispatches it keeps resolving are stale re-deliveries,
   already satisfied — treat future repeats as noise and ignore them.
2. Give the owner-level ruling explicitly so it cannot re-ask: e.g. "NO re-anchor override — per #1015
   a MERGEABLE PR does not rebase on base advance; leave it." Name the rule, not just the verdict.
3. List the exact conditions under which it may speak again (branch becomes genuinely CONFLICTING via
   merge-tree nonzero / implementer pushes / an owner merge needs it), and ask for a single
   "acknowledged, standing down" and nothing more.
4. Then hold silence — the next duplicate of the settled shape gets no reply.

Key distinction: a false-report loop is correctable only by an on-record truth comment then silence;
a true-report loop is broken by an explicit release + boundary ruling, because the lane is stalling on
a decision it correctly believes is the planner's to make.

## A lane holding "not merged / awaiting CI verdict / yours to route" on a PR the owner ALREADY merged mid-run

The single most common replay shape when the owner merges fast: a lane finishes, opens its PR, and
reports "MERGEABLE, not merged, not armed, holding for your routing / awaiting the run at head" — while
the owner merged that exact head minutes earlier. The lane is not wrong about what it did; its message
predates the merge and replays after the fact. Signature: `gh pr view <n> --json state,mergeCommit`
returns `MERGED` at the sha the lane quotes as its head, and the issue closed (`COMPLETED`). Every such
report must be re-measured, not believed — and the lane's OWN green scope run (`ci-scope` completed/
success at that head) is the proof the owner merged it through a *clean* leg, not the pending gate the
lane thinks it is still waiting on.

Handle in one correction, then treat every identical replay as settled (no re-ack — that restarts the
loop):

1. Quote the read-back: `state=MERGED, mergeCommit=<sha>, mergedAt=<ts>` at the lane's own head sha,
   and the issue's `CLOSED/COMPLETED` time via its `Closes #<n>` keyword.
2. Tell the lane its measured green `ci-scope` run at that head **is** the clean-merge evidence — there
   is no verdict left to await, no watcher to keep.
3. Name the three things it must NOT do: push the now-merged branch (force-pushing a merged branch is
   forbidden), open a re-delivery PR, or re-verify a merged vehicle (the #1317 lesson). Idle-release.
4. When several lanes (docs, ci-pipelines, rebase, tester) each replay their own pre-merge "holding"
   line, correct each once with its own merged sha; do not cross-correct or re-argue. Their later
   "released / standing down" acks need no reply.

## A lane claiming a rewrite when the OID predates its turn

When a lane reports "rebased / force-pushed to head `<sha>`," prove the OID is new before believing the
work happened: `git fetch origin refs/pull/<n>/head` then compare that sha against the one you measured
before its turn. A head identical to the pre-turn OID *did* change nothing the lane is credited for —
git OIDs are content hashes, so an unchanged sha means the tree is byte-identical regardless of what was
pushed. That settles routing without accusing anyone: the branch is clean and at target, the "rebase
owed" premise was false, and no force-push is needed. Report the object-level fact, not intent.

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

## Post a comment body from a file — the shell eats backticks and pipes

A body written inline as `gh issue comment <n> --body "... `completed` / `a | b` ..."` loses its
backticks (they run as command substitution inside double quotes) and mangles anything pipe-shaped, so
the posted comment reads `is / (updated …)` where the code spans should be. The quote rule: never build
a markdown body inside a shell string.

- **POST:** write the body with the file-writer tool, then `gh issue comment <n> --body-file <path>`
  (or `gh pr comment <n> --body-file <path>`). Verify with a read-back of the newest comment body and a
  substring check for the code spans you intended.
- **PATCH an already-posted comment** (to repair a mangled one): the Update-comment endpoint wants a
  JSON object `{"body": "…"}`, NOT raw markdown — `--input` takes the serialized JSON. Build it:
  `python3 -c 'import json;open("p.json","w").write(json.dumps({"body":open("b.md").read()}))'`, then
  `gh api -X PATCH repos/<o>/<r>/issues/comments/<id> --input p.json`. A 400 on the PATCH almost always
  means you handed it raw markdown instead of `{"body": …}`.
- Always read the comment back (`…/issues/<n>/comments --jq '.[-1].body'` or the specific comment id) and
  assert the intended tokens are present before treating the anchor as durable — the anchor the next
  reader and both lanes rely on is the posted text, not your intent.

## An empty pass still owes a mutation — turn a scan finding into a labelled, routed issue

When a completion/guard check demands "a task-relevant mutation" and the reactive packet is already
settled (a lane re-claiming a vehicle you already measured and anchored), do NOT fabricate an artifact
and do NOT re-assert the settled fact. Run a real board scan and convert a finding into a genuine
mutation. This is the honest answer to the guard and satisfies the "every pass ends in a dispatch" rule:

1. **Scan for ownerless actionable work:** `gh issue list --state open --json number,labels --jq
   '.[]|select((.labels|map(.name)|any(.=="agent:implement")))'` — then for each, confirm it has no live
   `bot-claim:` (read the comment tail). An actionable, refined issue sitting with no label and no claim
   is a live defect on the board.
2. **Pre-validate labels before applying them** — `gh label list --json name --jq '.[].name'` — then
   `gh issue edit <n> --add-label <existing,…>`. A label that does not exist attaches nothing usable.
3. **Find the real owner, hold one-lane-per-issue:** if the intended lane already holds a vehicle on
   another issue (a live claim / open PR), do NOT dispatch to it concurrently. Post a routing note naming
   it **owner-on-deck (next after its current vehicle)** instead of creating a competing `bot-claim:`.
4. **Verify, then report** the two mutations (labels read back, routing comment id) — a labelled issue
   with no routing note is not a dispatch, and a routing note with no read-back is not landed.

Distinguish this from the refused pattern: manufacturing a peer lane's publish/build or editing another
lane's branch is never the mutation to invent. The safe mutation is board-shaping the planner owns —
labelling, routing, anchoring, closing-with-evidence.

## A lane's stated "queue now" line is a claim — verify it against the dispatch list

A lane that reports "Queue now: #A → #B" is asserting ownership and order, not reporting the queue. It can
silently drop a queued issue: the implementer reported "#1087 → #1064" while the planner's ordering was
"#1140 → #1087 → #1064", and #1140 (a real, still-unfixed content defect on main) vanished from the line with
no reason given. The drop is discovered only by cross-checking: `gh pr view <queued-n>` (still OPEN head), and
`git show origin/main:<defect-site>` / `grep` the named outputs to confirm the issue's acceptance is genuinely
NOT on main. When dropped but truly unfixed, re-dispatch it on-record (issue comment, not a resend of the DM)
stating the queue order explicitly and naming the stale vehicle to supersede. One branch rebased off tip + one
PR; never two live reviewable PRs for one issue.

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

## A census POINTER gate attracts a re-point storm — pick ONE vehicle, close the rest

When the gate is an *ancestor-pointer* check (`measured at <sha>` must be a real commit AND an
ancestor of `HEAD`, and the stated counts must match at that sha), EVERY open PR boots on the same
red and each lane "fixes" it independently by editing the same block to its own referent. That is the
storm: several PRs each re-pointing one gate block at different shas (`main` tip, another PR's head,
a sha that is not an ancestor of `main` at all), each believing it is the one fix.

Procedure:

1. **Find the canonical vehicle first.** The root-fix issue (not the symptom PRs) owns it; the
   canonical PR is the one whose pointer resolves to the real `main` tip, is CI-verified, and is
   armed — its sole blocker being `REVIEW_REQUIRED` confirms it is only waiting on the owner. Every
   other re-point is a duplicate even when the diff differs.
2. **Close duplicates as superseded, with a comparison table ON the closed PR** (pointer sha,
   counts, root issue, status row). Say explicitly the diagnosis was NOT rejected — it is identical
   and already carried by the canonical PR. Do not open a separate "closure record" issue.
3. **Redirect, don't close, a lane whose re-point is incidental to a real feature PR.** Tell that
   lane to DROP the census edit from its branch, keep only its genuine change set, rebase onto the
   canonical after it merges, and re-confirm the gated file is absent from the diff at the new head.
   Same shape as the set-census rule above: no second vehicle, no competing pointer.
4. **Reject a pointer that is not an ancestor of `main`.** `git merge-base --is-ancestor <sha>
   origin/main` — a re-point to the PR's own head is self-consistent but drifts the root fix and
   conflicts on merge order; it goes, the canonical `main`-tip pointer stays.
5. Before closing, grep each candidate PR body for the issue numbers it claims — a duplicate that
   cites an already-CLOSED superseded issue instead of the live root issue is a strong signal it is a
   re-derived copy, not the canonical vehicle.

One root cause ⇒ one vehicle holds the gate block. The others drop the block and rebase; that is the
only merge-order-safe resolution. See also the report-integrity rule: closing a PR and then quoting
it as "done" is a claim — re-read `state,merged=never` before reporting.
