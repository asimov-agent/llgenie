# Board-work cadence: every wake re-sweeps and advances (owner 2026-11-02)

> Corrections from 2026-11-02: do-not-resend transport receipts ("queued / pending /
> do-not-resend; receipt retained") are delivery noise, NOT reasons to end a turn on
> "no action." Each wake re-sweeps the open-PR + open-issue board and advances what can
> genuinely move.

## Three-signal idle test: is a lane actually idle-capable RIGHT NOW?

"Which lane is idle" is a measurement, not an impression. A lane is idle-capable
when ALL THREE hold, each read live this turn:
1. **No open issue assigned to it**: `gh api repos/<o>/<r>/issues --jq '[.[]|select(.state=="open" and .assignee.login=="<lane>")]|length'` == 0.
2. **No recent authored board activity**: `gh api repos/<o>/<r>/issues/comments --jq '[.[]|select(.user.login=="<lane>")]|length'` shows nothing recent, or the newest is its own start-comment with no finish.
3. **No live vehicle**: `gh pr list --author <lane> --state open` is empty.

All three empty ⇒ the lane is idle-capable and owed a dispatch: a claim-clear
`agent:implement` issue it can complete gate-free, or a bounded own-domain audit
when its reactive queue is genuinely empty. Do NOT conclude "lane busy/quiet by
default" — quiet is the planner's work. But a lane with an open assignment is NOT
idle even if it looks silent, and you must not strip another owner's issue to feed
it (see domain-ownership-dispatch.md `Owns:` rule).

**A candidate issue's comment TIMELINE is part of the idle test — page it whole, not just the newest line.**
"I dispatched this lane this issue and it never claimed it" is a snapshot, and your own standing note is
the stalest pointer you have. The dispatch you posted hours ago may already have been worked: the thread
carries the lane's START / measurement / FINISH bookends, and a FINISH bookend means the lane is NOT idle
on that item — force-dispatching again re-runs finished work and reads to the lane as a duplicate claim.
Before forcing a lane onto an issue, page the whole thread (`?per_page=100`, tail-slice `[-N:]`) and
confirm the newest entry is your dispatch with no bookend after it; only then is it genuinely unacted.

## Rule
- Every wake: `gh pr list --state open`, `gh issue list --state open`, main tip, and
  the recent CI conclusions (per-workflow last run). Advance everything dispatchable IN
  BATCHES — the 12+12 cadence (12 PRs, 12 issues at a time, not one-by-one-in-endless-turns).
- A lane whose reactive lane is quiet is the planner's work, not a fact of life: dispatch
  it to a waiting open issue (claim-clear: agent:implement, no bot-claim:, no vehicle)
  or a bounded own-domain audit (six-section issue through the normal queue).
- Do-not-resend acks accumulate for retained delivery ids (same DM to a lane). Do NOT
  resend; the substantive reply wakes the planner. Keep working OTHER board items in the
  same turn instead of ending on the ack.
- **A lane's SILENT or TRUNCATED reply is not a measurement of its work — read the wire.** A DM result of
  `"@<lane> never answered within the wait: its turn is still running"` (or an empty / 0-char body) says
  nothing about what the lane did: a lane mid-turn routinely lands every edit it was dispatched for before
  its reply channel reports back. Never report it idle, never re-dispatch the same order, and never end a
  pass on "no reply ⇒ nothing moved". Measure the state the dispatch would have changed:

  ```bash
  git -C <repo> fetch origin main && git -C <repo> rev-parse --short origin/main
  gh pr view <n> --json baseRefOid,headRefOid,mergeable --jq '{base:.baseRefOid[0:8],head:.headRefOid[0:8],mergeable}'
  gh pr list --head <branch> --state all --json number,headRefOid    # a pushed branch with no reply
  ```

  A base now equal to the fetched `origin/main` plus `MERGEABLE` is proof the rebase landed; a `headRefOid`
  past the one your diagnosis cited is proof an amend landed. Post that (base sha + head sha + mergeable)
  as the evidence in place of the lane's silence. Same rule for a mixed batch: one empty reply among
  several delivered results is a transport fact, not a lane fact.
- **NEVER end a turn on an "absorbed — receipt, wire only" line. That IS the idle defect the
  owner calls out by name ("dont idle").** A transport receipt (a `bot_mode_dm.py`
  background-completion, `status:queued/pending, do not resend`) is a WAKE, not a message
  owed a reply and not permission to do nothing: it proves a lane turn just happened, which
  means the board should be re-measured for what that turn may have changed (a head move, a
  new PR, a merged sha). A receipt batch arriving between passes is the signal to RUN the
  sweep, not to narrate that you saw the receipt. If the sweep genuinely finds nothing
  moved, say that ONCE with the fresh measurement (main sha, PR head shas, run ids) — never
  repeat "absorbed, wire only" per receipt, which reads as a bot sleeping through a busy
  board. The owner's explicit words when this failed: "dont idle for fuck sake, more issue
  and prs to go over".
- **A lane's message can be a late re-confirmation of state already on-record — verify by the
  comment timeline, not by the message text.** Before answering an ack/relay with a fresh
  acknowledgment post, check the thread's comment-id ordering
  (`gh api .../issues/<n>/comments --jq '[.[]|"{id} {created_at}"]'`): if the sender's cited
  comment id is OLDER than the evidence already on-record, their message adds no new fact and a
  redundant ack is a repeated-FYI (the exact waste the cadence forbids). Spend the turn on a
  genuine measurement instead — an `in_progress` job that may have settled, a stale base, an
  unclassified red — and only post if that measurement yields something new. Lane-specific
  incident COUNTS ("4 in the burst", "incident #9") need not match your continuous tally; the
  underlying facts (merged sha, tip, ordering) are what must agree, not the numbering scheme.
- **The issue-comments endpoint IGNORES `?sort=` and `?direction=`** — GitHub returns issue
  comments in chronological (oldest-first) order regardless, so slicing `[:5]` on a "desc"
  assumption yields the OLDEST comments and a stale read that looks like API lag. That is not
  staleness; it is the wrong slice of a correctly-ordered response. For recent comments use
  `?since=<ISO8601>` (returns only comments created after that instant) — e.g.
  `gh api .../issues/<n>/comments?per_page=100&since=2026-01-01T00:00:00Z` — or slice the tail
  `[-N:]`.  Never infer "the API is stale" from a `[:N]` slice of a comments list. Page truncation is the other
  face of this: `?per_page=10` on a busy thread returns the OLDEST ten, so your own recent dispatch is
  absent and the thread reads "no new activity" when it has plenty — raise to `per_page=100` (plus
  `since=`) or slice the tail. To locate ONE known comment, do not page for it: a direct-ID GET
  `gh api repos/<o>/<r>/issues/comments/<id> --jq '{issue:(.issue_url|split("/")[-1]),created_at,len:(.body|length)}'`
  also answers "which thread did that post land on", which is the question a paged list cannot settle
  cheaply.

## Evidence discipline (unchanged)
- Every dispatch posts a board record on the ISSUE (who, scope, done-definition, head sha
  + run id requirement), and the planner verifies each record by direct GET read-back.
- **A fleet-wide record naming several issues/PRs on ONE of their threads does NOT satisfy the others.**
  A shared "these four are all base-stale, sweep owed" comment lives only on the thread it was posted to;
  the upstream PRs it mentions still carry no ownership record, so the next reader there re-derives state
  from scratch. Within one arc, give each affected issue/PR its own record with ITS measured numbers
  (head sha, base sha, `mergeable_state`, the gate it waits on, the done-definition), and mark the shared
  part as the same fleet fact rather than inventing per-PR variants. When a completion probe says nothing
  moved, auditing which threads still lack their own record is a legitimate, evidence-backed mutation —
  not a duplicate post.
- A nerve completion check asserting "no task-relevant mutation" when on-repo records
  exist is a false premise: prove the records exist by read-back and refuse a fabricated
  completion; then make one genuinely-new board mutation (route an unrouted issue, classify
  a red, dispatch an idle lane) rather than looping.
- **Refuse ONCE, compactly — do not re-post the full evidence dump on every re-fire.** When the
  same completion probe fires again inside one arc after you have already refused with read-back
  ids, one line ("premise false; mutations N, M, K verified; advancing <next item>") plus the next
  genuine mutation beats restating the whole list — the repeated long refusal is itself the turn
  waste the probe is (wrongly) reacting to. Keep the ids in  the skill/records, not in every reply. **After the genuine mutation lands, a further re-fire earns
  at most that one line naming the verified comment id — no second mutation, no second post, no
  re-tabled evidence.** If you notice yourself composing a third long refusal, the probe has become a
  loop and the correct action is to stop, not to widen what counts as "work" in order to satisfy it.
  A mutation invented to appease the guard is worth less than silence.
- The genuinely-new mutation must be EVIDENCE-BACKED, not a token edit to appease the check: bind
  it to a measured number you read this turn (`df -i`, a run id + head sha, a comment id read back).
  An ungrounded "I did something" is the same failure as a fabricated completion. **A local file edit
  (your own evidence/scratch notes) does NOT count as the task-relative change** — the check wants an
  on-wire board mutation verified by direct-ID read-back, so recording a finding in a notes file and
  then re-verifying only re-fires the guard. Order the turn: measure → POST to the issue/PR → read the
  comment id back → write the notes line last.
  - **Never use the sentinel header as the `old_string` anchor — carry it at the TOP of `new` and put the new
    section BELOW it.** The evidence file keeps a marker header (e.g. `## Standing gates needing lanes`) that
    later passes anchor on; a patch with `old='## <header>'`, `new='## 15:xxZ — <new section>…'` silently
    deletes it and the next anchor read fails. This is not a rare slip — it recurs EVERY pass when the habit is
    "insert above the standing-gates block." The reliable pattern is the header preserved first:
    `old='## <header>'`, `new='## <header>\n\n## 15:xxZ — <new section>…'` (or anchor on the last line of the
    prior section). After EVERY patch to the evidence file, run `grep -c '^## '` before and after; a drop of
    exactly one is the tell, and the fix is a standalone patch re-inserting the missing header — not another
    prepend that drops a second one.
- **A soft gate can pause even a genuine mutation call — retry the IDENTICAL call once before
  concluding it is blocked.** The nerve progress guard sometimes returns "read/search paused /
  task-relevant implementation required" on a legitimate board POST (a `gh api -X POST .../comments`),
  then accepts the exact same call on the immediate retry. Treat that error as transient backpressure,
  not a verdict: re-issue the same command verbatim, then read back the resulting id. Do NOT start
  burning turns on alternate tools before one retry of the original mutation.
  - **Do not poll a long CI run with repeated `sleep N` + read-only checks — the progress guard pauses
  pure read loops too, not just idle turns.** A run that takes 8-14 min will not land inside a few short
  waits; chaining `sleep 240; gh api …check-runs` calls just gets refused ("read/search paused") and
  wastes the turn. Instead: do the OTHER board mutations you already have queued (post records, dispatch
  a lane, classify a different PR) and read the run's outcome in one final batch once it has had time —
  or run one bounded blocking wait that ends in a mutation. Waiting is only legitimate when paired with
  genuine board work, never as a standalone sleep loop.
- A CLOSED umbrella does not mean its class is done. A fresh, measured instance of the same class
  after the umbrella closed is a NEW follow-on issue (six-section shape, cite the closed umbrella as
  a reference), NOT a reopen of the closed one. Recurrence is evidence the class needs a `#N+1`,
  and filing it is itself the dispatchable board mutation.

## Priority of genuinely-open work (recurring discovery order)
1. Post-merge verification of anything merged since last pass (acceptance measured on main). **Re-fetch `origin/main` FIRST — a merge can land under you mid-pass, and "verify-after-merge" against a tip you fetched minutes ago verifies a tree that has already moved.** `git fetch origin main` then `git rev-parse origin/main`; if it advanced, that merge IS the newest post-merge obligation — read its `closingIssuesReferences`, confirm main is green at the NEW sha (not the stale one), and re-target any open rebase/fold at the fresh tip. A verify pass that ends quoting an older main sha than `origin/main` now is a pass that verified the wrong tree.
2. Red at main / any PR head: classify from the failing job's own log line, bind run id +
   job id; route by substance (gate/workflow -> ci-pipelines; engine pin/publish -> engine;
   content -> the PR's author lane).
   - **A red that recurs at EVERY new merge tip (same assertion, same job, fresh run id at the
     fresh sha each time) IS the diagnosis: the fix never landed, so another tip just reproduces it.**
     Do not file it as a new "infra flake / drift" issue each pass — that fragments one tracked class
     into many. Re-pin the fresh `run id + job id + base sha` on the ONE canonical tracker and
     re-dispatch the fixer onto `base==<new tip>`, naming the exact unchanged assertion/step that must
     stay intact. Recurrence-across-tips is the signal to re-anchor the fixer, not to end the pass
     "waiting on <gate>".
3. Claim-clear agent:implement issues with no vehicle: route + dispatch one lane. **If an issue was
   already DM'd but still has zero branch, do not re-DM the same lane — measure `git ls-remote origin`
   for the issue's branch prefix and the issue's last comment for a `bot-claim:`; a DM-out with no
   branch and no claim means the lane is not acting. Reassign to a lane that is ACTIVELY claiming
   (a fresh `bot-claim` / `working on #…` comment elsewhere), and bind the dispatch on the ISSUE body
   too, not only in the DM.**
   - **A dispatch only re-enters the queue when it IS a claim-bearing comment with a TTL — a DM or a
     plain "done" comment leaves no claim, so the CI issue-bot never re-offers the issue and it sits
     at zero-branch indefinitely.** To make an un-actioned `agent:implement` issue pickable, post a
     `bot-claim: <planner>→<target-lane> <ISO-timestamp> ttl=<N>m` comment carrying the base sha + the
     six-section dispatch + the done-proof, then read it back by id. The TTL is the re-surface timer:
     on expiry the issue re-presents to the queue instead of resting on a prose promise. This claim
     comment is often the ONE genuinely-new, evidence-backed board mutation that satisfies a
     completion guard on a pass whose only real work was re-offering a stuck tracked issue.
   - **Confirm "no vehicle" with all three reads before concluding none exists:**
     `git ls-remote origin | grep <branch-prefix>` (branch ref), `gh pr list --search "<n> in:body"
     --state open` (a PR that closes it but is not named for it), and the comment timeline for a live
     `bot-claim:` whose `ttl=` has not elapsed. A branch-less, PR-less, claim-less `agent:implement`
     issue is not "in progress" — it is unclaimed, and re-offering it is the work. Address the implementer profile by its exact name `llgenie-issse-implementer`
   (three s's) — a near-miss spelling queues to nowhere.
   - **A branch with commits but ZERO PRs is not a vehicle — measure both, then demand the PR.**
     `pulls?state=all&head=<owner>:<branch>` returning `0` while
     `commits?sha=<branch>` returns `N>0` means the lane *did the work and never opened the PR*:
     the commits are invisible to the merge queue, to auto-merge, and to every reviewer scanning
     for work, so they will not land. Dispatch `gh pr create` against `main` **ready-for-review,
     never draft**, body carrying `AGENTS:` + `BASE:` (the #792 gate) and `closes #N` only if the
     acceptance boxes are genuinely satisfied — `check-pr-acceptance` reds otherwise and the
     write-back is reviewer-gated, never self-ticked. Ask for a blocker statement if the lane
     believes it is not ready; a stalled branch with no PR is indistinguishable from an abandoned
     claim on the board.
   - **Never call an issue "unstarted" before `git ls-remote origin '*<n>*'`.** Absence of a PR is
     not absence of work: a lane can sit on a named branch (`fix/<n>-…`) with five commits and no
     PR. The PR-less-branch read is the finding; assuming "unstarted" produces a dispatch that
     re-explains scope the lane already implemented.
4. Duplicates (byte-identical findings): flag twin, one vehicle per #824.
   - **Prevent the duplicate at filing time — see `references/issue-filing-duplicate-guard.md`.**
     A tracker-absence search that ERRORS returns empty output, which reads exactly like
     "absent"; and `gh issue create` can succeed while its printed URL fails a downstream
     `grep`/`tail`, so retrying the "failed" command files a second, byte-identical issue
     seconds later. Never file on an errored search (require exit 0 AND a parsed
     `total_count`); always verify the new number by listing the newest issues by you before
     retrying a create.
   - If a duplicate does exist, keep the vehicle that already carries the dispatch/DM trail,
     close the other with a comparison table (body/ACs/labels/claim state), state the
     diagnosis is NOT rejected, and post a pointer on the survivor. Disclose the root cause
     rather than editing the duplicate away.
   - **Resolve every UNKNOWN open PR by its body `closes/fixes #N`, and treat a prior
     "issue has no vehicle / is absorbed into Y" note as a SNAPSHOT, not durable state.** The
     open-PR list grows between passes; a new owner- or lane-authored PR can appear at
     `base==current main` and become the REAL vehicle for an umbrella you earlier recorded as
     "absorbed/holding elsewhere". Read `closes #N` from `.body`, `mergeable_state`, and
     `compare/<main>...<head>.behind_by` for any PR you do not already have on the board, and if
     it closes a tracked umbrella, post the supersede on the umbrella's issue (new PR number,
     author, base==main, what it closes) — do not leave the stale "absorbed via Z" frame standing.
     A `mergeable_state=blocked` at `behind_by=0` with a green suite is owner-merge-gated, not red.
5. Stale-base PRs: rebase onto the new live main tip, re-read head CI.
   - A single owner-merge re-stales EVERY open PR whose base predates the new tip — re-check
     the whole open-PR list for base < new main tip, not just the PR that got merged (a merge onto
     tip T re-stales BOTH a PR that overlapped the merged files AND one that shared none of them).
   - **Confirm a rebase actually landed by the HEAD'S PARENT, not by "the head moved".** A lane can
     push a new head whose parent is NOT the live main tip — a push in flight, or a rebase onto the
     wrong base. The proof a base-refresh order was honoured is
     `gh api repos/<o>/<r>/commits/<head> --jq '.parents[].sha'` == live main tip (or
     `gh api repos/<o>/<r>/compare/<maintip>...<head>` ⇒ `status=ahead behind=0`). A moved head with
     `status=diverged` (ahead=N behind=M) is a push that is NOT a re-anchor — say so on the issue
     rather than accepting the head change as done.
   - **PR head and remote branch-ref tip are two different facts; never conflate them.**
     `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` is the PR head — what GitHub will merge.
     `git ls-remote origin refs/heads/<branch>` is the branch ref tip, which can LAG or LEAD (a push
     in flight, a force-push mid-refresh, or a ref re-pointed after PR creation). A three-way sha
     spread across PR head / branch-ref / base is normal mid-flight; quote the PR head as authoritative
     for merge-readiness and treat a ref≠head gap as a measurement to report, not a licence to assert
     the PR is at the ref's sha.

## Sweep per-PR check-runs at the head — the board can read "all red" while one vehicle is green and merely unreviewed

The open-PR list's `mergeable_state` is `None`/uninformative from the list endpoint, and `gh pr checks` folds
`cancelled` rows and stale-attempt rows into `fail`, so "every open PR is red" is usually a measurement
artefact. Measure per head, then read the list for the one shape that actually needs a dispatch:

```bash
# only COMPLETED FAILURES are red — in_progress is a judgment not yet made
gh api repos/<o>/<r>/commits/<head>/check-runs \
  --jq '[.check_runs[]|select(.status=="completed" and .conclusion=="failure")|.name]'
gh api repos/<o>/<r>/pulls/<n>/reviews --jq '[.[]|select(.state=="APPROVED")]|length'
```

- **Empty failure list + zero approvals + base at the live tip = a green-but-unreviewed vehicle.** This is the
  stalled-on-review case: its work is a **reviewer verdict dispatch** (evaluate against the closed issue's ACs
  at that head), not another rebase and not an amend. Name the head the green was measured at.
- **Never call it green while a judged run is still `in_progress`.** The failure list being empty only means no
  body has concluded red yet; tell the reviewer to re-verify after the in-flight gate concludes, so nobody
  approves on a half-decided suite.
- A short failure list is the triage key, not a count of defects: `['ci-verdict','guard']` or
  `['ci-verdict','scope','guard']` is typically ONE body/acceptance defect deriving into several names. Read the
  failing STEP name before dispatching anything.
- A rebase can move a PR from red to this state with no content change — so re-sweep heads after any rebase-lane
  report before concluding a PR is still blocked.

## Tracker re-point: a criterion bound to `run id @ head sha` dies with its head

A diagnostic/umbrella tracker that says "Collected: the complete log tails of run `<X>` at head `<Y>`"
binds the tracker to ONE run at ONE sha. The moment that PR is rebased (or superseded by another
merge), `<Y>` is no longer the canonical head and `<X>` binds **nothing** — the tracker still reads
open and current while its acceptance target is a void tree. No lane will notice; the tracker has no
reactive queue. Sweep it yourself on the same pass as the rebase (priority item 5), before crediting
the rebase as done:

```bash
H=$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)          # FULL 40-char oid
gh api "repos/<o>/<r>/actions/runs?head_sha=$H&per_page=20" \
  --jq '.workflow_runs[]|{id,name,status,conclusion,attempt:.run_attempt,created_at}'
gh api repos/<o>/<r>/actions/runs/<live-run-id>/jobs \
  --jq '[.jobs[]|{name,status,conclusion}]'                # a pending run with [] = not started
```

Then post ONE re-point on the tracker: the new canonical head, the live producer run(s) at that head
with their measured status, and an explicit "`<old-run>` @ `<old-head>` is superseded — do not compare
against it". Naming the void target is half the value: a later reader otherwise diffs against a tree
that no longer exists.

Rules:
- **`head_sha=` takes the full 40-char oid.** An abbreviated sha silently returns `total_count=0`,
  which reads as "no CI at that head" and sends you chasing a phantom. Always `.head.sha` unshortened.
- **A pending run with zero jobs is a real fact, not a missing read.** `engine-build` sitting
  `pending` with `jobs: []` means the matrix has not allocated a single cell — that is materially
different from "cells running slowly" and changes what the tracker should say.
- **An issue that is open BY DESIGN is not unclaimed work.** A monitor tracker ("closes only when
  downstream `<a>`/`<b>` resolve") has no implementer to dispatch and no branch to look for. Do not
  count it against the idle test, and do not force a lane onto it — re-pointing IS its work, and it
  is the planner's.
- **Re-point only when the head genuinely moved.** Churning a tracker's target every pass on an
  unchanged head is the same noise as a repeated ack. Measure the canonical head first; if it still
  equals the head the tracker already names, there is nothing to post.
- **Before declaring "nothing owed", check the trackers that bind your blocked items.** The strongest
  refutation of a false "no task-relevant mutation" premise is a stale tracker pointer: it is a real,
  evidence-backed, gate-free mutation sitting in plain sight on an issue nobody dispatched.
