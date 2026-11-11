# Incident closure, board mutation, and one-vehicle routing

How a planner *finishes* an incident so the next reader finds it — not just reports it in a DM.

## Closing an incident is TWO deliverables
1. **Verify the acceptance criterion on `main` at the merged tip.** A PR head that was green does not
   mean the merged `main` is green: the merge can introduce a race the PR head never saw. Quote a
   *completed* run at the merged-tip sha — `gh run view <id> --json status,conclusion,headSha` — not
   `gh pr checks` and not a PR-head run.
   **A burst's post-merge acceptance is its own consolidated deliverable, separate from the incident comment.** After an auto-merge burst, do NOT let "I filed the incident" stand in for acceptance: post ONE table (PR | merge commit | gates at its head measured | acceptance criterion held-on-main?) covering every merged PR in the window, and name the honest remainder (a PR whose own re-verify still waits on a rebase, a red-by-construction PR already ruled to close). Filing the incident and verifying acceptance are TWO commits; a pass that reports the burst but never verifies the merged tree has left the standing duty un-done.
   **If that run is still `in_progress` when your turn has to end**, do not claim green and do not wait
   idle: land the verification comment anyway, stating the acceptance criterion as measured *in the
   merged tree* (quote the file/line you read at the merged-tip sha), the run id, and explicitly "green
   not yet observed — re-verify on conclusion". That comment is the durable anchor; the re-verify is a
   tracked todo item. A "no green claim" comment plus a hold beats both a fabricated green and silence.
2. **Make the incident a durable board mutation.** A comment/claim on the issue, a filed vehicle, or a
   corroborating comment on the owning umbrella. "Resolved" typed into a DM or a ledger is *not*
   closure — the board must show it. A planner turn that ends on narration with no board write is the
   failure mode: an escalation report that lives only in the planner's private memory does not exist
   for the next reader.

## Is the merge an incident or a legitimate landing? Check the merge authority
- Before reporting "a bot merged on its own", read `gh pr view <n> --json mergedBy,mergedAt,reviewDecision,reviews,autoMergeRequest`
  **and** the reviews separately: `gh api repos/<o>/<r>/pulls/<n>/reviews --jq '[.[]|{state,by:.user.login,t:.submitted_at}]'`.
- **Owner-account merge + `APPROVED` is a legitimate landing ONLY if the approving identity differs from
  the merging identity.** When the approver `by` == `mergedBy` — the fleet's `asimov-agent` merge token
  approving and merging its own PR, commonly seconds apart — that `APPROVED` is SELF-approval, not an
  owner decision: it is the unapproved-merge incident, even though `author_association` reads `OWNER` and
  `reviewDecision` reads `APPROVED`. A merge by a bot identity with no review, or one still
  `REVIEW_REQUIRED`, is the same incident class.
- **Only a `state:APPROVED` review is an approval — a lane's `state:COMMENTED` review reading "all
  acceptance met" is a review, not an approval.** A PR can carry a human lane's glowing COMMENTED
  review AND still have its ONLY APPROVED be the merge token; read every review's `state`, and when the
  sole `APPROVED` is the merging identity the lane's comment changes nothing — it is still the
  self-approval incident. Counting a COMMENTED-with-praise review as an approval is the exact false
  negative that reports an unapproved merge as legitimate.
- **A PR merged while BLOCKED at an owner-gate thread is unapproved by definition.** A routing comment that
  says "no auto-merge, owner's pick required" cannot stop the workflow: if `mergedAt` postdates that hold
  and no human pick exists on the gate thread, report it as unapproved regardless of the `APPROVED` review.
- **Evidence to gather for the incident report:** the approving review's `submitted_at` vs `mergedAt` (the
  seconds-gap is the tell); the auto-merge workflow run that did it
  (`gh api "/repos/<o>/<r>/actions/workflows/auto-merge.yml/runs?per_page=5"` → match head sha + time);
  `autoMergeRequest` (null AFTER a merge is expected — it does not disprove armed-then-consumed); and whether
  the class fix ever shipped (`git show origin/main:scripts/auto_merge.py | grep -n 'try_approve\|APPROVER_TOKEN'`
  — if `try_approve` still approves with the merge token, the fix is UNSHIPPED). Name the run id and the
  cumulative instance count in the report, and state plainly that the planner armed/merged nothing.
- An approval that appeared *after* your last measurement is not stale state to reconcile, it is new
  information: compare timestamps (review submitted-at vs your earlier read) before calling anything stale.
- **Arming auto-merge when the owner says "auto-merge" — the WORKFLOW is the owner-approve mechanism, the arm is parallel, and a `do-not-merge` hold is what really defers (measured on #1806).** Read the owner-approved design BEFORE assuming "owner must click":
  * The repo's **`auto-merge.yml` workflow IS the automatic owner review+merge**: on a green CI completion it runs `make auto-merge APPROVE=1 APPROVER_TOKEN=${{ github.token }}`, and `scripts/auto_merge.py` approves a `MERGEABLE`+`BLOCKED`+`REVIEW_REQUIRED` PR as `github-actions[bot]` (a DIFFERENT identity than author `andyholst`, so GitHub allows it) then squash-merges with the owner PAT. That is the "reviewed by the owner, no click" branch behavior.
  * **The workflow DEFERS (never merges) on: `do-not-merge` label, state!=OPEN, draft, not-MERGEABLE, mergeStateStatus!=CLEAN, head moved, or review not clearable.** It posts ONE deferral comment per head (`<!-- auto-merge: deferred <sha> -->`) naming the reason. **When #1806 sat BLOCKED/REVIEW_REQUIRED it was because `do-not-merge` was set the entire time the sweeps ran** (owner-placed 17:44:33Z → removed 18:04:42Z) — the hold deferral, NOT a missing owner-approve mechanism. Find the deferral marker on the PR and read its reason before calling it an owner-click gate.
  * A planner-side native arm (`gh pr merge <n> --squash --auto`) only **waits** on every gate — it never approves. It is redundant when the workflow path exists, and is not "the owner approval". If you arm it, read `autoMergeRequest` BACK via GraphQL (`enabledAt` + `mergeMethod`; exit 0 does NOT mean armed — `--auto` arms nothing when the base is not the default branch) and **name both ids in the dispatch/record: the PR id (`#n`) and the owner/approver account (`asimov-agent`)** so the next reader can trace which PR, pending whose approval, armed at which time. After the owner's hold is lifted and CI is green the workflow's own approve+merge fires on the next completion or the `:03,:33` cron — the "owner auto-approve" the user expects is that workflow, not a planner click.
  * Stop at armed+verified: never approve, never merge "on the owner's behalf", never fabricate an approving review to unstick your own arm. A reviewer's verdict comment declaring "all criteria ticked N/N" is proof in the COMMENT; if the PR body's `- [ ]` boxes are still unticked on the wire, that is a body write-back discrepancy — record it and leave the body alone, do not upgrade the comment's claim into a green you did not observe.

## A merge INCIDENT is a WINDOW, not the one PR you tripped over — sweep every merge since your last tip

When `main` has moved past the tip your last verified pass recorded, **enumerate every PR merged in that
window before filing the incident**. Auto-merge bursts: a lane pushes a batch of green PRs and the job
merges several within minutes, so the first one you notice is rarely the only one. Filing per-PR produces
N near-identical incident comments and under-states the count the owner needs.

```bash
# every PR that merged since the tip you last verified (prefer git log over the pull list)
git fetch origin main
git log --oneline <your-last-verified-tip>..origin/main            # the merge commits, one per PR
gh api 'repos/<o>/<r>/pulls?state=closed&per_page=40' \
  --jq '[.[]|select(.merged_at!=null)|{n:.number,by:.merged_by.login,at:.merged_at,mc:(.merge_commit_sha[0:8])}]|.[0:10]'
```

- **One incident, one amendment.** If you already filed naming a subset, do **not** open a second incident:
  post an `## AMENDMENT` comment on the SAME umbrella with a table (PR | approver+review id | merged-at)
  covering the whole window, and state explicitly that it corrects the earlier under-scoped count. A second
  comment naming the extra PRs is a correction, not a duplicate.
- **`merged_by` on the burst merges reads `null` in the pull payload even though the PR is `merged:true`** —
  the auto-merge job's token does not surface as `merged_by`. Resolve the authority from the REVIEW instead:
  `pulls/<n>/reviews` → the `APPROVED` review's `user.login` + `id` + `submitted_at`; if the approver is the
  `asimov-agent` auto-merge identity and its timestamp is seconds before the merge, it is the self-approval
  incident class regardless of the null `merged_by`.
- **A lane reporting "OPEN / MERGEABLE / NOT armed / nothing merged" is stale evidence, not a contradiction.**
  The auto-merge job self-approves under the owner token and fires the instant a head is clean — `autoMergeRequest`
  reads `null` AFTER the merge and was never "armed" in the board sense the lane means. When you find the PR
  actually `merged`, correct the lane on-record (DM + a line on the umbrella) with each PR's review id and merge
  time; do not accept their "nothing merged" as current.
- **Measure the outcome before you alarm.** A burst of self-approved merges is the incident, but if every
  merged head was gate-green, every PR closed its own issue, and no acceptance criterion is red at the tip,
  say so plainly and recommend NO revert — the incident is the authority defect (recurrence of the same
  self-approval), and reopening green landed work is a different, out-of-scope action.

## Every merge to `main` is a stale-base event — dispatch the rebase lane to MEASURE
- The instant a PR lands, every open PR is behind `main`; `BLOCKED`/`DIRTY`/`UNSTABLE` on those PRs is
  now ambiguous between "stale base", "owned by another lane", and "genuinely conflicting". Resolve it
  by measurement, never by blanket rebase.
- Dispatch the rebase lane to produce a per-PR table: number | `mergeable` (CONFLICTING vs MERGEABLE) |
  genuinely-conflicting? | owning lane | proposed action — then wait for your word before any rebase.
- Only a PR whose `mergeable=CONFLICTING` is a rebase candidate. A head that is merely behind, or red on
  a gate, is not: rebasing it churns a branch the gate will re-evaluate anyway and fights its owner.
- **Hands off branches another lane owns.** A bump/automated batch's red is usually the *gate defect*
  (e.g. an event-frozen base sha sweeping already-merged commits into the closing/scope check), not a
  conflict; rebasing cannot clear it and the branch belongs to its producer. Name those PRs in the
  dispatch as out of scope, with the reason.

## One vehicle per finding — route to the OPEN umbrella, never duplicate
- Before filing a new tracking issue, `search/issues?q=repo:<r>+<slug>+in:title+state:open`. If an open
  umbrella already owns the class, **post corroborating evidence there as a comment** and extend its
  proposal with the *new* question — do not open a duplicate ticket. **But a search hit that shares only the
  label DOMAIN or the owning lane is NOT the same defect — read the candidate's `## Problem` section before
  deciding.** Two issues both labelled `ci-pipelines` + `agent:implement` can name entirely different gates (a
  fleet of workflows left `disabled_manually` vs one gate returning "no verdict" at a merged tip); folding the
  second into the first buries two root causes under one title and hides the new one from its owner's queue. The
  test is the named failure mechanism, not the label set: same mechanism → corroborate on the existing umbrella;
  different mechanism → file separately and say in the new body which neighbouring issue you checked and why it
  is not the same.
- Never reopen a closed/merged issue as the vehicle for new work; file a NEW one and say explicitly
  what it supersedes.
- When the umbrella carries a **settled DECISION thread**, read those decision comments first. An
  umbrella can record e.g. "design X is NOT adopted, for this reason" that your evidence would silently
  contradict. Reconcile (agree, or state the exact premise that changed) — do not append a contradiction
  as if the thread were blank.
- **Before posting a pointer/link comment that ties an existing tracker to another thread, grep the
  target thread for the ticket number — a second pointer is the same duplicate-note defect as a re-post.**
  `gh api repos/<o>/<r>/issues/<n>/comments --jq '.[]|select(.body|test("<ticket>"))'` returning empty is
  the licence to post; a hit means the reference already exists and the update belongs as an edit or a
  follow-up, not a fresh comment. "No duplicate vehicle" also means "no duplicate reference to the
  vehicle" — the reader of the thread needs one authoritative link, not two.

## A recurring alarm class files a fresh tracker per occurrence — close the duplicates against the ONE canonical, keep it open

The filing side above is "one vehicle per finding". The CLOSURE side is its mirror: when the SAME class
alarm arrives as several near-identical six-section issues within hours (a run that instantiates zero jobs
and hangs `pending`, a wedged matrix, a repeated gate red), the board is accumulating *alarms*, not work.
Handle it as dedup, not as N tickets:

- **Canonical stays OPEN.** The tracker that owns the class is the one home. Fresh per-occurrence trackers
  are closed against it; the canonical is never closed while the class is still producing instances.
- **Say why on the thread FIRST, then close with `state_reason=duplicate`.** Post the dedup rationale as a
  comment (which canonical, that the class is live, what happens to the fresh evidence), then
  `gh api -X PATCH repos/<o>/<r>/issues/<n> -f state=closed -f state_reason=duplicate` and read `.state`
  + `.state_reason` back. One call carries both fields — no second PATCH needed.
- **A fresh occurrence of a LIVE class is not a settled duplicate — the evidence fold is the owning lane's
  call.** If the fresh tracker's cited run is still `in_progress`, do NOT fold its run id into the canonical
  body yourself and do NOT describe it as concluded: name the fresh run id in the close comment as "to be
  folded by the owning lane when it concludes" and leave the canonical evidence list alone. Writing a live
  run id into a settled-evidence list misstates an in-flight job as a finished one.
- **One tracker per class, not one tracker per alarm.** Closing the duplicates (with readback) is a real,
  in-authority board mutation and a legitimate guard-clearing one: it collapses a recurred class back to a
  single home instead of N open rows all recording the same failure — and it is not a peer-lane edit.

## Verify a posted comment independently
- **Post board mutations one at a time.** A parallel tool batch whose calls each POST a comment posts
  the note once per call — the thread then carries N identical planner comments and the next reader
  cannot tell which is authoritative. This holds even when the two POST commands **differ** —
  `gh pr comment <n> --body-file` and `gh api repos/<o>/<r>/issues/<n>/comments -F body=@<file>` both
  write to the same thread; two DIFFERENT commands in one batch are still two POSTs and still
  duplicate the note. Batch the *reads* (issue state, comment list, PR checks) and serialize the
  *writes*: one POST, read back its id, then the next. If duplicates already landed,
  delete the surplus ids (`gh api -X DELETE repos/<o>/<r>/issues/comments/<id>`), re-list and assert the
  note appears exactly once, and state the accident on the thread rather than quietly cleaning up.
- **An empty POST response is NOT a failed POST — it is an unread one.** When a `gh pr comment` /
  `gh issue comment` call comes back with blank output (the relay dropped it), do NOT immediately re-post:
  the comment very likely landed. Capture the body to a file and post once with redirection, then read the
  collection back before any retry:
  ```bash
  gh pr comment <n> --body-file /tmp/note.md > /tmp/post.out 2>&1; echo rc=$?; cat /tmp/post.out
  gh api "repos/<o>/<r>/issues/<n>/comments?per_page=100" --jq '.[-1]|{id,at:.created_at,login:.user.login}'
  ```
  The rule "serialize writes, one POST" is violated just as badly by *retrying an unread* POST as by
  batching — a blind retry on empty output is the exact path to N identical planner comments. Deleting
  surplus ids is recovery, not the standard; `gh api -X DELETE .../issues/comments/<id>` returns 204 with
  no body, so a clean exit code is the success measure there (do not pass `-o /dev/null`, which is invalid
  for that call).
- **An empty stream is an UNREAD stream, and that holds for a whole tool stall, not just one POST.** When several
  commands in a row — including `echo` / `true` — come back blank, the tool channel is stalled and nothing about the
  mutation is known: re-run a trivial command to test liveness, then decide from the ARTEFACT (the issue body, the
  comment list, the label array), never from the absent output. And never write a verification/record saying "not
  posted" while a command's output has not returned — the write can land after your claim, so a failed-then-done
  record is as dishonest as a fabricated success. Read back first, then record the state the wire shows.
- **A PR's ordinary comment thread lives at `repos/<o>/<r>/issues/<n>/comments`, NOT `pulls/<n>/issues/comments`.**
  The `pulls/<n>/issues/...` path does not exist and returns HTTP 404 `Not Found` — do not read that as
  "the PR has no thread". Plain comments share the issue-comment namespace (a PR consumes an issue number);
  `pulls/<n>/comments` is only the separate inline *review*-comment collection.
- The issue-comments endpoint ignores `sort`/`direction`; read the newest with `?per_page=100` + `.[-1]`,
  never `per_page=1&direction=desc` (that returns the oldest comment and looks like a lost POST).
  **`sort=created&direction=desc` does not rescue it either** — a `?per_page=3&sort=created&direction=desc`
  read returned a comment from another author hours older than the one just posted, which reads as "my POST
  did not land" when it did. The mechanism is the same: the parameter is ignored, so the page is server
  order. Read `?per_page=100` + `.[-1]`, or skip the list and GET the id you already have (next bullet).
  **`sort_by(.created_at)|.[-1]` over an unpaginated list sorts PAGE ONE only** — on a long thread (30+
  comments) it returns a comment from a previous day and reads as "my POST never landed". For any
  verification of your own post use the direct-ID GET (`issues/comments/<id>`); when you genuinely need the
  thread's newest, page through with `--paginate` first.
- **A guessed comment id 404s, and that 404 is NOT evidence the POST failed.** Comment ids are global and
  sparse, so the "next" id for your post is neither `previous+1` nor a digit you can reconstruct by
  incrementing a neighbouring comment's id (`…553` guessed for a real `…753` returns `HTTP 404: Not Found`).
  The id in the URL your own `gh issue comment` prints (`…/issues/N#issuecomment-<id>`) is the source of
  truth for the read-back; parse it from that output, or take `.[-1].id` from a `?per_page=100` list, then
  GET `issues/comments/<id>` and quote `issue_url`, `len(body)`, `user.login` as the proof. Never report a
  lost POST, and never re-POST, on the strength of a 404 from an id you made up.
- Confirm a comment landed by *listing* the issue's comments and matching id + author + first line:
  `gh api repos/<o>/<r>/issues/<n>/comments --jq '[.[]|{id,login:.user.login,at:.created_at}]'`.
- The url/id returned by your own `gh issue comment` / `.[-1].id` call is **not** independent proof —
  it is a self-echo, so the proof is the collection GET at that id, not the POST's own output. The id
  itself, though, IS authoritative: use exactly the one the POST printed rather than deriving a
  neighbouring one (previous bullet). A read-back that quotes `issue_url` + body length + author, and
  matches the issue you meant to comment on, is the standard — a bare "posted" from the POST's exit code
  proves nothing about which thread received it.
- Filing a vehicle: `gh issue create --body-file -` then `gh issue view <n> --json state,title,labels`
  and quote the readback (OPEN + labels present).
- **`)`-clean two-call create: title+body first, labels second — never three field styles in one POST.**
  Passing `-f title=…` alongside `-F body=@file` **and** `--input labels.json` in one call returns
  `gh: Invalid request.` (the `--input` JSON body and the `-f/-F` form fields conflict). Create with only
  the form fields, then PATCH the labels with a raw JSON body:
  ```bash
  gh api -X POST repos/<o>/<r>/issues -F "title=<t>" -F "body=@/tmp/body.md" > /tmp/created.json
  N=$(jq .number /tmp/created.json)   # the create's own echo is a self-echo, still read back next
  echo '{"labels":["continuous-improvement","agent:implement"]}' > /tmp/labels.json
  gh api -X PATCH repos/<o>/<r>/issues/$N --input /tmp/labels.json >/dev/null
  gh api repos/<o>/<r>/issues/$N --jq '{n:.number,labels:[.labels[].name]}'   # the real proof
  ```
  Keep the body prose free of raw double quotes when it goes through a JSON payload; a `.json`-linting
  write tool refuses the whole write on one unescaped character.
- **Filing is a CREATE, not a routing.** The create+label readback is only step one; the same turn must
  land the owner-lane dispatch *on the issue* (scope / out-of-scope / acceptance / done-condition, verified
  by comment id) plus a DM — see `domain-ownership-dispatch.md` ("A filed-and-labeled finding still needs
  an on-issue ownership comment"). A pass that ends on "issue filed" has produced a ticket nobody is
  working, indistinguishable on the board from an unowned idle row. Create → label → on-issue dispatch,
  all three, before the turn's work counts as a mutation.

## A recurrence is a CLASS gap — file ONE tracked class issue, not the Nth per-instance fix

When the SAME gate reds on a THIRD branch/lane for the same structural reason (each lane rediscovering
it independently by CI failure), the per-instance fix is not the whole job: the class has no tracked
owner, so it will re-fall. Recognise the pattern (`grep`/count the same error stem across this week's
red PRs; check no OPEN issue's title already names it — `gh api --paginate .../issues?state=open` filtered
on the error stem), then file ONE six-section issue that names the recurrence explicitly
("3rd recurrence: <branch A>, <branch B@sha>, <branch C>") with `continuous-improvement` +
`agent:implement`, routed to the domain-owning audit lane (docs-change-note → documentation-maintainer;
gate/pipeline → ci-pipelines-maintainer). State in the issue that the live instances stay owned on their
own vehicles — the class issue owns the *practice/guard*, not the in-flight PRs. Do not weaken the gate to
close the class; the fix is making the practice first-class, not relaxing the check.

## Force an idle-capable lane onto gate-free work
- When every reactive lane is parked on a real gate, the *planner-owned* work that has no vehicle yet
  (a live→tree profile fold, an untracked drift) is the thing to file and route — not a reason to idle.
  "Waiting on the gate" is not "so I file nothing".

## When a completion/authority check fires again after you already mutated
- A repeated "no task-relevant mutation" / completion challenge is not answered by re-posting or
  re-verifying the last mutation — that reads as narration. Ask *what is still genuinely open in my own
  work* and make a **distinct** board mutation: a dangling reference your own tickets created (an
  umbrella every ticket cites but nobody filed), an unrouted `agent:implement` issue, an unverified
  acceptance criterion, or a fix vehicle carrying a narrower label set than the class it closes.
- **Do the mutation in ONE terminal call with the body inline, not `write_file` → POST.** A progress
  guard that pauses "read/search/test-only actions" treats a scratch `write_file` as a non-mutation and
  will block the follow-up `gh api -F body=@file` even though the file is the payload. Build the note as
  a shell variable and POST + read back in the same call:
  ```bash
  BODY='Closure: <evidence, ids>'; \
  gh api repos/<o>/<r>/issues/<n>/comments -F "body=$BODY" --jq '{id,at:.created_at[0:19]}'; \
  gh api repos/<o>/<r>/issues/<n> -X PATCH -f state=closed --jq '{state}'
  ```
  The same guard also blocks a comment-POST followed by an issue-PATCH split across two calls — combine
  the comment and the state/label change into one call so the turn's single visible action is the
  mutation, never a posted note that is read as narration.
  **It pauses READS as well as writes**, so a pass that is mid-investigation (a `runs?head_sha=` GET to
  confirm a gate) stalls where it stands. Order the turn mutation-first: land the outcome comment you
  already owe, then resume the read — the mutation unblocks the channel. Nothing clears it except that
  mutation; re-reading, a scratch file, or a more detailed narration of what you were about to check
  leaves the pass blocked with the work still unrecorded.
- **When comment-POSTs and backlog label fixes are both refused, mutate the ACTIVE board, not archaeology.**
  A completion probe that rejects a verified comment and a long-tail backlog issue label is telling you the
  mutation must touch the issue the fleet is *currently* working. The reliable in-authority change is a
  severity label: a live-main-red fix issue carrying `agent:implement`+`agent:refined` but **no severity** is
  a genuine active-board gap (nothing marks it as the priority it is). Replace the label set with a raw JSON
  body and add `severity:high` (or `severity:critical` for a main `unit`/`top-tier` red), then read it back:
  ```bash
  gh api -X PATCH repos/<o>/<r>/issues/<n> --input <(echo '{"labels":["agent:implement","agent:refined","continuous-improvement","severity:high"]}') >/dev/null; \
  gh api repos/<o>/<r>/issues/<n> --jq '[.labels[].name]|join(", ")'
  ```
  Labels available: `severity:critical`, `severity:high`, `severity:medium` (`gh api .../labels | grep severity`).
- **Assignment is NOT a verifiable mutation — do not count it.** `gh api -X POST .../issues/<n>/assignees
  -f assignee=<login>` (and `-F assignees='["<login>"]'`) both exit 0 while the readback stays
  `"assignees": []` — the bot token that authors every lane under one identity cannot set assignees, and the
  lanes route by LABEL anyway. A silent 0-exit assign is exactly the "successful call ≠ successful task" trap:
  always read `gh api .../issues/<n> --jq '.assignees'` back, and when it is empty fall back to the label
  mutation above rather than re-trying the assign.
- Inspect your own artefacts for incoherence before inventing new scope: "every one of these tickets
  cites an umbrella that does not exist" is a real, in-authority gap and its fix is a real mutation.
- If the challenge names a state that is plainly no longer current (it verifies a sha the board has
  moved past), record it as advisory evidence and act on the board, not the challenge text.
- **A live-profile skill edit you made is a SILENT PRIVATE EDIT until it is versioned in-tree — filing that versioning is the reach-for planner-owned mutation when the guard fires and the only remaining fix is peer-lane.** When a completion/progress guard demands a mutation but the outstanding fix lives on another lane's branch (implement the owning lane's `scripts/` change for it) — that edit is forbidden, refuse it. The correct bounded mutation that IS yours: a `skill_manage` patch to your own live skill/reference (or any live-profile edit) is a private edit the moment it lands, and the lane self-versioning rule (#791/#1777) owes it as an issue + PR committing the text under `agents/<profile>/` (docs-only, `SYNC: <profile> make sync-agent-profile PROFILE=<profile>` for any `agents/<profile>/` diff, `closes #N` + `## Acceptance criteria`). File that issue, dispatch it to the implementer (docs-only rulebook text is implementer-queue work; a lane's own SOUL/skill is that lane's self-service work only when the lane is not the one filing), leave the dispatch trail on-issue, and read the ids back. That closes the private-edit gap with a real mutation instead of manufacturing a peer-lane edit.
- **The challenge can arrive MANY times in one session, each AFTER a PASS receipt on the last mutation.**
  A verified on-wire POST + a PASS verdict does not stop the next challenge landing. Do not treat each new
  one as a fresh demand to invent scope, and do not loop `verify → PASS → new challenge → verify`. Answer it
  with AT MOST ONE genuinely-new mutation grounded in a MEASURED delta, then stop.
- **Never post a "no-delta re-measurement" / "nothing changed this pass" comment to clear a challenge.**
  That is the duplicate-narration failure this section warns about, wearing an evidence costume: it mutates
  the thread with content whose only purpose is to exist. If the measurement shows no delta anywhere, the
  correct action is refusal (prove the mutations you already made by direct read-back of their comment ids)
  — not a timeline entry saying nothing moved.
- **The mutation that reliably clears it is a REAL measured delta, found by measuring several threads in ONE
  call and conditionally posting only the one that moved.** Sweep the live gates in a single script and
  branch on the result; post exactly one comment on the item whose state actually changed since your last
  read, then direct-ID GET it back in the same call:
  ```bash
  python3 - <<'PY'
  # measure: a sweep run's cell census, a commit's check-runs at head, a PR branch tip
  # e.g. did a gate that failed PRE-tick RE-RUN after the tick and now succeed?  that is the delta
  # if run.completed and a previously-in_progress cell concluded -> post the final census
  # if a check re-ran with a NEW started_at > your last-read tick and changed conclusion -> post that
  # POST the single delta comment, then GET /issues/comments/<id> and assert id+issue+len
  PY
  ```
  A gate that reds at a head only because it ran BEFORE a reviewer's tick, then re-runs to `success`
  afterwards, is the archetype: the red was stale-in-time, and recording the fresh green run (with its
  `started_at`) is a genuine, non-duplicative mutation that also tells the lane it may now arm.
- **When the standing task is an owner-directed action on a specific thread and the lane's DMs are queued/pending
  (delivery receipts say "do not resend"), the ON-ISSUE comment is the authoritative channel.** Post the task,
  the measured evidence (frozen tip, no claim), the exact command, and the done-criteria on the issue itself;
  record that DMs are queue-blocked so the thread is binding. That is a legitimate task-relevant mutation, not
  a re-nudge, and it does not violate "do not resend" because it uses a different transport.
- **Bounded: inspect ONCE, then stop.** Look for a genuine gap in your own artefacts; if there is none,
  do not keep manufacturing scope to appease the probe. Prove the mutations you already made with a
  direct read-back of their specific comment ids (`gh api .../issues/comments/<id> --jq '.id,.user.login,.issue_url'`)
  and end the turn. A probe whose premise is provably false ("no mutation attempted" while those ids
  exist on the API) is REFUSED, never appeased. Posting a duplicate comment just to clear a check is
  fabrication with extra steps — it corrupts the exact trail the board exists to keep honest, and a
  completion challenge is not authority to invent work. Same when the demanded mutation would touch a
  peer lane's branch: report `auto=none (probe demand, not owner instruction)` and refuse.
- **A falling PASS confidence / rising ESCALATE probability across successive verifies IS the signal to stop.**
  Verifying three same-class mutations in one session measurably degraded the verdict (1.0 → 0.72 → 0.48,
  ESCALATE 0 → 0.37) even though each POST was real and read back. Treat that drift as the instrument telling
  you the mutations are now narration-shaped: stop posting, prove your existing ids by direct read-back, and
  end the turn. Manufacturing one more "fresh" comment per challenge (a re-phrased escalation record, a
  restated gate state) after the measurement shows no delta is the duplicate-narration failure with an
  evidence costume — and the board pays for it with a polluted trail.
- **An "escalation record" only clears a guard when the escalation threshold itself crossed a measured line.**
  A comment that says "still unclaimed, next step = escalate" is a genuine mutation ONLY when the elapsed
  time / lane-response evidence is NEW since your last record on that thread (quote the elapsed figure and
  what you cross-checked for liveness). Posted twice with the same facts and a new timestamp, it is a
  timeline entry whose purpose is to exist.

## Tick a peer tracker's acceptance checkboxes to the EVIDENCE, and leave a diagnostic MONITOR open while its fix carriers are separate

- **"Declared complete" is not "checklist ticked."** A lane that posts a final classification/closing
  comment can leave the issue body's `- [ ]` acceptance items unticked, so the board shows an open,
  unverified checklist beside a "complete" comment. The planner MAY edit a peer tracker's body — issue
  shaping is planner authority, not a peer-lane branch edit. Confirm each item is actually satisfied by
  the posted evidence (quote the job ids / verbatim lines the comment carries), then tick the boxes and
  read the count back. **Count criteria ROW-AWARE, never with a bare `grep -c '\[x\]'`** — that matches
  inline prose and checkbox mentions elsewhere in the body and over-reports (measured: a body with 6
  criteria rows, 5 ticked, returned 6 on a loose grep). Parse the rows and report both states:
  ```bash
  gh issue view <n> --repo <o>/<r> --json body --jq '.body' | python3 -c "
  import sys,re; b=sys.stdin.read()
  c=re.findall(r'^- \[(x| )\] (.*)', b, re.M); t=sum(1 for k,_ in c if k=='x')
  print(f'{t}/{len(c)} ticked'); [print(('  [x] ' if k=='x' else '  [ ] ')+s[:70]) for k,s in c]"
  ```
  Tick to evidence — never ahead of it. Confirm the exact unticked row(s) by title, not a count, before
  deciding the tracker is 6/6 versus 5/6.
- **A diagnostic MONITOR issue stays OPEN while its downstream fixes ride separate carrier PRs.** An issue
  whose purpose is classification/monitoring (diagnose a run, grade cells) is DONE as a diagnostic when its
  evidence lands, but you do not close it "by declaration" while the fixes it identified are still open on
  their own vehicles — those merge and close on their own trails. Leaving the monitor open holds the findings
  visible; closing it early orphans the follow-on context. Tick its acceptance, note the downstream carriers,
  and leave it open.

## A lane's gated RECOMMENDATION is a snapshot, not an order — re-measure the subject's lifecycle before dispatching

"#N needs a further rebase onto <main>" / "the write-back is not actionable yet" is a claim about when it
was measured, exactly like "ready for review" (see `verifying-lane-claims.md` §6o). Before you relay it or
schedule the action, re-read the subject:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{state,merged,merge_commit_sha,head:.head.sha}'
gh api repos/<o>/<r>/issues/<linked> --jq '{state,closed_at}'
```

Typical dissolve: the PR MERGED at a LATER head than the one the lane measured, so "needs a rebase onto the
newer main" is moot; the red they saw at that now-abandoned pre-merge head is an already-tracked
phantom/base-drift gate class, not a regression of the subject. Relaying it un-rechecked sends a lane to
rebase a merged branch. Correct the lane on-record (comment id + readback) and DM it to drop the premise.

## A closed issue with unchecked ACs is not automatically a closure-honesty defect — find its tracker and measure the rollout first

A merged PR closing a multi-lane AC ("each affected lane carries X / a pointer / a copy") leaves the
umbrella `- [ ]` on the wire. That is not yet a finding. Run three checks in this order — each can dissolve it:

1. **Count rows row-aware** (the python row parse above), never `grep -c '\[x\]'` across the whole body.
2. **Search the open board for a tracking vehicle**: a premature umbrella-close tracker (open,
   `agent:implement`) that names the rollout AC means the gap is tracked — corroborate THERE with evidence,
   do not file a duplicate.
3. **Measure the rollout per-lane on fetched `origin/main`, never by filename alone.**
   ```bash
   git ls-tree -r --name-only origin/main agents/<lane>/ | grep -i <topic>
   git grep -l -iE "<procedure phrase>" origin/main -- agents/<lane>/
   ```
   A lane can carry the pointer INLINE in its `SKILL.md`/`SOUL.md` without a dedicated
   `<procedure>-pointer.md`, so a filename-only check reports "MISSING" and manufactures a false gap.
   Then look for the remaining lane's in-flight vehicle (`gh api repos/<o>/<r>/issues?state=open`;
   `gh api repos/<o>/<r>/pulls/<v>/files --jq '.[].filename'`).

Only when there is NO tracker AND NO in-flight vehicle is unchecked-at-close a genuine new finding. An AC
that is 5/6 landed with the 6th in flight is "tracked to a landing, not citable proven yet" — say that and
correct the reporter, do not open a ticket.

**When you DO file that new vehicle, link it back on the CLOSED issue so the `unproven: N` row resolves forward.**
A closed issue carrying `- [ ] unproven: 1. <criterion>` is a legitimate reviewer hold, but on a CLOSED thread it
is also a dead end: the next reader who tries to resolve that criterion finds no pointer to where the work went
and re-derives (or re-files) it. After filing the tracked vehicle, post ONE linkage comment on the closed issue:
the vehicle number, its dispatch comment id, and one line of the evidence that made the defect live. State
explicitly that the AC state is unchanged (closed + reviewer-gated — no tick, no untick) and that the comment is
purely a forward reference. That is a real, non-duplicative board mutation (it closes a dead end the board
previously had), and it is the correct counterpart to this section's "do not open a ticket" rule — the ticket is
ownable, the linkage is what keeps the closed row honest.

**Post-merge, read the MERGE side before flagging any unchecked AC:**
- **A `(proven: … head=<sha> …)` citation stays honest after the merge even though `<sha>` is no longer the
  live tip** — the merged PR's head becomes an ANCESTOR of the merge commit. Prove reachability with
  `git merge-base --is-ancestor <cited-head> <merge-commit-sha>` (rc=0 ⇒ reachable in `main`) instead of
  re-anchoring the citation to the new tip. Re-anchoring a still-reachable citation is churn, not verification,
  and it is exactly the "cite the live head" reflex that gets it wrong here (the cited head is deliberately
  the graded one).
- **An unchecked box followed by a `- unproven: N. <criterion>` line is a LEGITIMATE hold, not an untick a
  merge skipped.** The reviewer recorded that criterion as not-yet-proven; do not tick it, do not read the
  `[ ]` as a closure-honesty defect, and state the hold as correct. Only an `- [ ]` with NO explaining
  `- unproven:` marker is a candidate defect — and even then run the three checks above first.
- **Find what a merged PR actually closed by reading `.body` for `closes/fixes #N`, then re-read that issue's
  `state`+`closed_at` and its AC block.** A PR body can close an issue OTHER than the one its title names
  (a verdict/attribution PR closing the diagnosis issue, not the feature issue) — verifying the title's issue
  instead of the `.body`'s `closes` target checks the wrong ACs.

## Pitfalls
- **Compare shas at EQUAL LENGTH, or compare them whole — a mismatched prefix length fabricates "the branch moved".**
  A conditional that tests `sha[0:10] == prefix` where `prefix` came from a truncated log/dispatch line (8
  chars) is always false, so a frozen branch is reported as MOVED and the wrong claim goes on the wire. Take
  the full 40-char `head.sha` from the API and compare prefixes of the same width (or `git rev-parse` both
  sides); when a "moved" verdict appears, re-measure the tip directly before posting. If the false claim
  already landed, post a superseding CORRECTION naming the bad comment id and the measured tip — same turn.
  **The mechanism is exact string comparison, and it bites every "unchanged?" branch, not just `head`:**
  `sha[:10] != "a3db2f11"` is True for the SAME commit (10 chars vs 8), so a `base == main` check
  fabricates "base drift" just as readily as a tip check fabricates "moved". Never compare a slice
  against a hand-typed literal of another length — slice both sides to one width, or compare the full
  40-char shas from the API. **Print the widths in the call that decides to post**
  (`print(len(a), len(b), a[:10], b[:10])`); the length mismatch is the bug announcing itself. And do
  not treat a prefix match as identity — same-commit questions go to full-sha equality or
  `git merge-base --is-ancestor`.
- **A tracker/umbrella body's PROGRESS line goes stale the instant its cited PR merges or its cited blocker changes — patch it, don't just comment.** An umbrella body that reads "#X rebased + all-CI-green (head …)" or "implementer PR gate-free and openable now" is a claim the next reader (implementer, reviewer) sees FIRST; once #X merges (to a new `main` sha) or the blocker becomes owner-gated, that line is wrong even though your merge/block fact is already in a comment. This is the rule-33 class — a new fact about an object declared healthy — and it is an in-authority planner body EDIT (issue shaping is planner authority, not a peer-lane branch edit). Procedure: fetch the body (`gh issue view <n> --json body --jq '.body' > /tmp/b.md`), replace the stale sentence(s) with anchors asserted present, re-check the canonical gate on the patched body BEFORE posting (`python3 -c 'import issue_body; print(issue_body.missing(open("/tmp/b.md").read()))'` → `NONE`, and `## Technical` last), then `gh issue edit <n> --body-file /tmp/b.md`, then READ BACK on the wire (`missing() NONE`, `grep -c` of the old stale phrase == 0). Verify before AND after; a gate-clean local body is not proof the POST preserved it.
- **A label that asserted a state the PR has since left is stale board state — correct it when you record the new state.** A PR marked `needs-review` while green, which later reds a gate, still reads `needs-review` until you remove it; that tells the next reviewer an unmergeable PR is ready to review. When you land the red-gate diagnosis, also `gh api -X DELETE repos/<o>/<r>/issues/<n>/labels/needs-review` in the same turn and read the label list back empty. A held review on a red PR is the same defect as a red PR with no owner: the board misstates the work. (Do NOT place `do-not-merge` as a substitute — that needs a filed remediation issue per the standing rule; removing a now-false readiness label is the lesser, correct mutation.)
- **`gh api` cannot set a label array from `-F labels=@file` or from repeated `-f labels=X`.** `-F labels=@file`
  sends the file's text as a single string and GitHub rejects the PATCH (`Invalid request`); repeating
  `-f labels=a -f labels=b` lets the later field override the earlier one instead of building an array.
  Replace a label set with a raw JSON body: write `{"labels":["a","b"]}` to a file and
  `gh api -X PATCH repos/<o>/<r>/issues/<n> --input <file>`, then read back
  `gh api repos/<o>/<r>/issues/<n> --jq '[.labels[].name]'`. When you are *adding to* a set rather than
  replacing it, `gh issue edit <n> --add-label a --add-label b` is the simpler, less error-prone path.
- **A fix vehicle inherits its parent class's routing labels.** A verify/drift-origin issue tracked on
  `agent:implement` + `continuous-improvement` whose fix vehicle was filed with only `agent:implement`
  drifts off the surface the parent is tracked on. When routing a spearhead vehicle, copy the parent's
  label set onto it and read it back — a vehicle labelled narrower than the class it closes is invisible
  to whichever board filter that class uses.
- **The `agent:refined` tracker is its own label, and it attaches to the ISSUE, not the PR.** Two recurring
  misses to audit whenever routing: (a) an issue whose body already carries a measurable acceptance / a
  concrete cause→fix spec IS refined, but if it lacks `agent:refined` it falls off the refined-queue filter —
  read the body for a measurable done-condition (a Prove-the-guard line, a named gate + expected rc, a test
  count) and add the label, don't eyeball the header and skip it; (b) **the ISSUE sitting behind a live PR is
  easy to forget** — you route the PR, verify its head, and never check the parent issue, which can be `open`
  with ZERO labels. Enumerate every issue in your routing set and confirm the full
  `[agent:implement, agent:refined, continuous-improvement]` (or `agent:refined` alone when it is a parent
  class) before you consider the routing pass done; a bare issue behind a green-looking PR is an unowned row
  the board cannot see. Sample one pass, fix all missing labels as raw-JSON PATCHes, read each back.
- **`-f` and `-F` are not interchangeable in `gh api`: lowercase `-f` posts the file path as the literal
  body.** `gh api .../comments -f body=@/tmp/note.md` exits 0 and creates a comment whose entire text is
  `@/tmp/note.md` — no error, no warning, ~13 bytes where the note was 1.5 KB. Only `-F body=@file` reads
  the file. Same for `gh issue create -f body=@file`. The tell is a body length wildly below the file size
  on the read-back (`jq '.body|length'`), so measure length, never the exit code; a wrong-body comment must
  be PATCHed in place (`gh api -X PATCH .../comments/<id> -F body=@/tmp/note.md`) rather than reposted, or
  the thread gains a duplicate.
- **A heredoc/`write_file`-built body MUST be re-read for length before it is trusted anywhere.** Same
  class as the `-f` slip: a 30-byte body on an issue whose source file is 3.5 KB means the payload was
  interpolated as a reference, not expanded.
- **Heredoc python with nested jq string-concat** (`".[-1].id+\" \"+.user.login"`) throws
  `SyntaxError: unexpected character after line continuation`. Post and verify in separate simple calls;
  keep jq expressions out of python string literals.
- **DM ≠ board.** A dispatch sent by `message_agent` is not durable ownership; the issue must carry the
  claim comment with the sha/branch/scope or the next lane re-derives (or re-does) the work.
- **The owner has no `message_agent` handle — escalate on the board, not by DM.** `message_agent` to the
  owner identity (e.g. `asimov-agent`) returns "No teammate named …" and lists only lane profiles. Do not
  burn turns hunting an owner DM target: post the escalation as a comment on the owner's review-queue /
  pinned planning issue, naming the defect, the evidence ids, and the exact decision you need, and state
  plainly that nothing was armed. That comment is the durable escalation; the owner reads the board.
- **A handoff/compaction note's \"prior pass already patched X (N chars)\" is a CLAIM, not a fact — measure
  the artefact before reconciling or re-patching.** Run `wc -c <file>` and `grep -n '<section header>'
  <file>` first; a note that says a fix is \"N chars, still to reconcile\" when the file is far larger and
  already carries the block sends you to redo finished work. A stale \"still to reconcile\" line in a
  compaction summary costs a whole turn — verify on disk, then either act or record \"already complete\"
  and move on. The same discipline as \"a bot's report is a claim; the API is the evidence,\" applied to
  your own earlier self.
