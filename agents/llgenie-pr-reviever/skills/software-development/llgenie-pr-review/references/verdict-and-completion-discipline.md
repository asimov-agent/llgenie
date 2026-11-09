# Verdict and completion discipline (llgenie PR review)

Rules for the *state* of a review — when it is done, how it is recorded, and when to
stop. These apply on top of the gate/evidence rules in SKILL.md.

## A completion/progress guard firing is NOT evidence that work is owed

When an internal reflex reports "task-relevant change required" after the review is
genuinely complete, the honest moves are:

1. Re-read the live wire (PR head sha, check-runs, issue box marks) and confirm what,
   if anything, is actually owed.
2. If nothing is owed, **say so plainly** — do not invent activity to satisfy the
   reflex.

Do NOT fabricate progress. A duplicate GitHub comment, a second verdict, a redundant
re-tick, or a throwaway skill/scratch edit is not a review artifact and pollutes the
record. The verdict plus the seam tick ARE the deliverable; once both are on the wire
and verified, the review is done regardless of what a reflex asserts.

**Why it bites:** manufacturing a second verdict or re-tick against an already-resolved
head creates exactly the stale/contradictory wire state that later dispatches then
misread — the reflex that demanded "a change" is satisfied by making the record worse.

**When the guard is not advisory but BLOCKS further reads, clear it with a genuine durable artifact — never a duplicate wire mutation.** A blocked tool call wants a change; the honest change is real work product: a consolidated decision record (the adjudication trail — head graded, the measured facts, why the disposition holds vs. clears, the on-wire comment/box ids) written to the profile cache/scratch, or a strengthening patch to this skill capturing the new nuance. Both are artifacts a future dispatch legitimately reads. A second comment, a redundant re-tick, or a throwaway scratch write is not. Write the real artifact, verify it on disk/on-wire, then state plainly that the review is complete; do not manufacture wire churn to appease the guard.

**Before concluding "nothing is owed", check whether a load-bearing finding lives only in an UNDELIVERED message.** `message_agent` can return `queue_full` with an `evidence_file` — that is a LOCAL artifact, not a wire delivery: the planner/peer never received it, and a finding whose sole disposition is a queued DM is effectively undelivered. The most genuinely-owed artifact under a guard is therefore often a finding that belongs on the PR/issue thread (where the owner and the merge lane read it) but was only ever sent as a DM — post it there (verified by direct comment id), then report. This is the announce-where-the-work-lives rule applied against the queue: a DM that did not land is not a disposition.

## A finalize step is verification-first and idempotent — never report "landed" before reading the wire back

The step that posts the verdict comment and runs the `--proven` write-back is a
**commit**, and a commit that can replay (tool-output echo, retry-on-timeout, a
re-read that looks empty so you send it again) will duplicate the record. Guard it:

1. **Pre-check for idempotency.** Before posting, read the live body at the head sha
   and count the `- [x]` boxes carrying `(proven: … comment=<id>)`. If that count
   already equals the criteria count at this head and the cite matches a posted
   verdict, the review is **already landed** — reuse the existing comment id, post
   nothing, PATCH nothing. A replay must be a no-op, not a second comment.
2. **Assert before declaring success.** Only after posting, read back and require:
   exactly one verdict comment with the id you posted; body ticked-box count ==
   criteria count; every `(proven: comment=…)` equals that one id. Report "landed"
   only when all three hold.
3. **A 0-ticked read against a posted N/N verdict is never "landed".** That is the
   ambiguous read a verification-first commit must resolve by re-reading the wire —
   report "unconfirmed, re-read the wire", never re-post and never assert success.
4. **Refuse to PATCH a moved head.** The write-back records the sha it judged and
   re-checks the live head before PATCHing; a head that advanced past the verdict's
   sha invalidates the write-back.

**Comment-id capture — `gh api …/comments --jq '.[0].id'` returns the OLDEST comment, not the one you just posted.** The default list ordering is ascending by id, so `.[0]` is the first-ever comment on the thread; on a busy PR the write-back's `verdict-ref comment=<id>` then names a stale unrelated comment. Three safe sources for the id of the comment you just posted, best first: (a) **POST via `gh api` and read the id from the create response itself** — `gh api repos/<org>/<repo>/issues/<n>/comments -f body="$(cat draft.md)" --jq '.id'`. The `POST …/comments` endpoint returns the created comment object, so its `.id` is unambiguously the one you just made; this is race-safe where a list read is not (a peer's comment landing between your post and your read makes `.[-1]`/descending theirs, not yours). Then confirm it resolves on-wire: `gh api …/issues/comments/<id> --jq '{id,user:.user.login,created_at}'`. (b) capture it from `gh pr comment`'s own stdout — it prints the full comment URL ending in `…/issues/comments/<id>`. (c) as a last resort read `.[-1].id` / sort descending, and re-verify `created_at` is minutes old and the body is your verdict. Assert the id you will cite resolves on-wire to a comment whose `created_at` is minutes old and whose body is the verdict you wrote (`gh api repos/<org>/<repo>/issues/comments/<id> --jq '{id,created_at}'`) before PATCHing. A `body[0:60]` slice inside an object-constructor shorthand (`{id, body[0:60]}`) is a jq syntax error — build it as `{id, created_at}` or `{preview:(.body[0:60])}`. Also, a pipe inside a compound boolean filter binds looser than `and`/`or`, so `select(.user.login=="me" and .body | startswith("BOT"))` applies `startswith` to the whole boolean and errors `… cannot be applied to: boolean`; parenthesize the piped sub-expression — `select(.user.login=="me" and (.body | startswith("BOT")))`.

**A FILTERED list read over the default page can return `[]` for a comment you just posted — an empty filter is not "not posted".** `gh api …/issues/<n>/comments --jq '[.[]|select(.body|startswith("X"))]'` reads only the default page (30, oldest-first ordering not guaranteed to include the new one), so a successful post followed by a filtered census can print `[]` while the comment exists. Never re-post on that empty result (it is the duplicate-record failure). Verify by the **direct id read** — `gh api …/issues/comments/<id> --jq '{id,user:.user.login,created_at}'` — and use `?per_page=100` when you genuinely need a census.

**`gh issue comment` takes NO `--json`/`--jq` flags — passing them aborts BEFORE the post, so the comment never exists.** Those flags belong to `gh api`, not to the `gh pr comment`/`gh issue comment` subcommands; a chained `gh issue comment <n> --body-file f --json id --jq .id` prints the subcommand's help and exits non-zero *without posting*. Do not treat stdout that merely lists the usage as "posted but id-capture failed" — the record is absent. Post clean (`gh issue comment <n> --body-file f`), then read the id back from `.[-1]` and **confirm the latest comment is your login and matches your draft body** (`gh api …/issues/comments/<id> --jq '{id,user:.user.login,created_at,head:.body[0:60]}'`) — if the latest comment is still a peer's, your post never landed and you must re-run it.

**A write-back to an issue already `closed`/`completed` is legitimate — it records acceptance history, not a reopen.** An issue can close when the change ships elsewhere (a value re-landed on main via a sibling PR) while its acceptance boxes remain the record of which criteria the reviewed PR proved. PATCHing its boxes after closure is not a revive and needs no reopen; `acceptance_writeback` applies fine to a closed issue. Do check the closure actor and `state_reason` (`gh api …/issues/<n> --jq '{state,state_reason,closed_at}'` plus the `closed` event's `actor`) so the verdict comment states WHY it is closed and does not imply the merge/close was yours (#1088).

## A head can move AFTER the verdict+write-back landed — a squash-onto-base is a re-anchor, never a re-tick

A head can rebase/squash onto the base *after* you posted the verdict and ran the
write-back. The two shas then have **byte-identical trees** but the new one is not a
descendant of the old — it was reparented onto the base. Tell this apart from a real
content change with two commands, never by eye:

```bash
git diff --quiet <old> <new> && echo IDENTICAL     # empty ⇒ same tree, no content change
git merge-base --is-ancestor <old> <new> && echo descendant || echo NOT-ancestor   # false ⇒ reparented
```

`IDENTICAL` + `NOT-ancestor` is a **landing-squash**: the evidence you measured holds
(same tree), only the commit identity changed, so the verdict-ref's `head=<old>` is now
an orphan sha. The honest remedy, in order:

1. Post a **re-anchor comment** on the PR naming the new sha as the grading head and
   quoting the empty-diff + not-ancestor checks as the proof it is a landing-squash,
   not a content change. Say plainly the verdict stands, re-anchored.
2. **Re-run `check-pr-acceptance` at the new head** — it re-reads the issue body LIVE,
   so a drop in the violation count (e.g. 8→5) is the evidence the write-back tick
   landed against the live issue, at the new sha.
3. **Never re-tick** an already-ticked issue and **never re-post a fresh verdict** — a
   landing-squash owes neither (same rule as the superseded-head case above). The
   write-backs' `head=<old>` in their `verdict-ref` is now stale but not wrong; the
   re-anchor comment is the authoritative head for grading.

**Why it bites:** a squash-rebase of a clean branch is routine and lands silently
between your read and your report; if you treat the moved sha as a new head to grade
you re-review identical bytes, and if you treat it as unchanged you leave a verdict
citing an orphan sha with no re-anchor — the next reader cannot tell which sha the
verdict applies to. One empty-diff read settles which case it is.

## A defect on another lane's branch is delivered as a PROPOSED PATCH comment — never an edit

This lane never edits another lane's branch (no push, no rebase, no branch edit), but it is often the
only lane that finds the one-line defect. The deliverable is then a comment that makes the fix
reproducible by the owner without re-deriving it. Include, in this order:

1. **The graded head sha and the file's blob sha at that head** — `git rev-parse <head>:<path>` — so the
   reader can confirm the line they are changing is the line you read, even after the head moves.
2. **The exact line number and its current text**, quoted verbatim.
3. **A ready-to-apply replacement block**, not a description of one. A prose "the cadence claim should be
   withdrawn" costs the owner a re-derivation; a before/after pair costs them one paste.
4. **Why it clears the gate, traced to the criterion's own words.** Show which limb of the criterion the
   edit satisfies, with the measurement that killed the other limb — so the owner can see it is not
   optional polish. State plainly that the other criteria are already ticked with measured proof, and what
   the issue stands at (e.g. "7/8 until this lands").
5. **Say plainly that this lane did not touch the branch**, so the record never implies an edit.

Verify the comment landed by direct id read-back (`gh api …/issues/comments/<id> --jq '{id,user,created_at}'`
plus a grep that the suggested replacement text is present) — a proposed patch whose body lost its code
block is worthless, and a filtered list read can return `[]` for a comment that exists.

**Do not route such a defect to `## Not covered` to unblock yourself.** Out-of-scope is for work that
belongs to another vehicle; a one-line fix in a file this PR already touches is in scope and the owner can
apply it in a minute. Marking it out of scope converts a trivial defect into a permanent exemption.

## A peer's "your watcher is still aimed at the zombie / your claim is false" is itself a snapshot — verify live processes and the on-wire record before killing, re-aiming, or retracting

A dispatcher correction routinely asserts two things at once: (a) a factual claim of yours is false, and (b) an action is owed ("kill the watcher on run X and re-aim", "retract your satisfied claim"). Each half is a claim about state at the peer's read time; verify each independently before acting — one can be true while the other is stale.

1. **Verify the factual half on the wire** (e.g. the ancestry test: `git merge-base --is-ancestor <run_head> <live_head>`). If the peer is right, accept it plainly and name the exact check that proved it. If the peer is right but the ACTION is a no-op because you already did it, say so — accepting the fact is not obeying a stale instruction.
2. **Verify the ACTION half against live state, not the peer's premise.** "Kill the watcher on run X" is a claim that such a watcher is RUNNING. Read the live process table (`ps -ef | grep -E 'watch|<run-id>'`) first. If the only live watcher is already on the VALID run/head and no process polls the zombie, there is **nothing to kill** — the re-aim was already done. Report that, don't kill-and-restart a correct watcher to satisfy a stale premise (a needless restart loses the poll progress it already accumulated).
3. **Never retract a claim you never made.** Before posting a "retraction" of "your X claim", search the actual comment bodies on the thread (`gh api …/issues/<n>/comments` and scan for the quoted claim). If no such claim exists on-wire, do NOT fabricate a retraction of a phantom — post a factual record that (a) confirms the peer's load-bearing fact, and (b) states the current true state (watcher aim, live run ids), so the thread carries reality rather than a denial of something you never said.

**Why it bites:** obeying the stale half either restarts a working watcher (churns the build the queue is correctly waiting on) or manufactures a retraction for a claim that was never posted (a fabricated record). The two halves — "is the fact true?" and "is the action already done?" — have different answers and each needs its own read.

## A peer re-dispatching against a SUPERSEDED head

A peer can re-dispatch "the boxes are still unticked / post the unblock verdict" citing
a head, a violation count, and a run that are all **older than the seam tick you already
completed**. Before re-ticking or re-posting:

- Re-read the live PR head sha, the live issue's box marks, and the cited run's
  `created_at` against your tick time.
- If the boxes are `- [x]` and the verdict exists, **no work is owed** — post ONE
  correction naming the comment id of the seam-produced tick, state "no re-tick"
  (#1644 stays verdict-gated), and stop.
- Never post a second write-back against an already-ticked issue.

Trust the live wire (head sha, issue `edited_at`/`updated_at`, each box's mark, run
`created_at` vs tick time) over a peer's textual claim. A threshold veto surfacing "N
violations" on a run created *before* the tick is the faithful hold at that moment, not
evidence the fix failed.

**A dispatch's named head can be a WHOLLY WRONG sha — not old, not superseded, just not the branch's head.** A peer (even the one that looped the PR's CI) can hand you "PR #<n> is ready at head <sha>" where `<sha>` is neither the live head nor any ancestor of it — an unrelated tree they mis-read from another run or branch. Before doing any re-head work (re-review, re-test, re-anchor, re-tick), read the head from the PR object itself: `gh api repos/<org>/<repo>/pulls/<n> --jq .head.sha`. If it differs from the dispatch's sha, there is NO re-head owed — you already graded the live head; say so plainly, name both shas, and do not manufacture a re-anchor against a branch state that does not exist. Optionally confirm the reported sha is unrelated (`git merge-base --is-ancestor <reported> <live>` false AND `git diff --quiet <reported> <live>` non-empty) so the "phantom" claim is evidence, not assertion. A re-anchor is legitimate only against the sha `pulls/<n>.head.sha` actually returns.

### A delayed/stale DM can demand you UNDO a correct reconcile — never obey a peer instruction that reverses verified wire state

Messaging is durably queued and can be delivered LATE: a peer may read a DM you sent
*before* your last correction, then ask you to "re-apply the tick / reach the state you
describe" — where the tick it names is the exact over-tick you already un-ticked. The
queued DM describes a state that no longer exists; the peer's *instruction* is built on
it. Obeying re-introduces the defect.

Procedure when a peer asks you to change a box/verdict whose live state contradicts the
peer's premise:

1. Re-read the authoritative wire (`updated_at`, the exact box line, the comment id) and
   compare it to what the peer quotes.
2. If the wire already holds the honest state, **do not re-apply**. Identify the quoted
   state as stale (old verdict comment id, superseded head sha) and reply naming the
   comment id of the correct ingest and the live `updated_at`.
3. Never re-tick/re-post merely because the peer asserts a count. "The honest home is
   the tracked issue, not a re-tick into compliance" applies to the peer's own routing,
   not just your judgement — if the peer earlier said #<n> is the fix home, a later
   "re-tick it" from the same peer contradicts that and does not override it.

**Why it bites:** the reviewer is the only lane that can un-tick, so an obedient re-tick
silently re-documents a defect as delivered; the stale DM's author cannot see that it
arrived post-correction. The wire is the tiebreaker, not the message text.

## A peer's "the only live cell" claim is itself a run-state snapshot that ages — re-read every referenced run's jobs, and CANCELLED is no-verdict

A dispatcher hand-off routinely states a run's *current* state as fact ("the fresh
push=true producer is cancelled, but the only live cell right now is run X @sha, and
the other verdict-gated criteria still ride on X"). That sentence describes run state
at the peer's read time, not at yours — and state moves in minutes. Before binding it
into a write-back or a hold:

1. **Re-read EVERY referenced run**, not just the one the peer flagged. `gh api …/runs/<id>`
   for `{status,conclusion}` and `gh api …/runs/<id>/jobs` for each job's `conclusion`.
2. **A job can be `cancelled`, not `in_progress`.** The run a peer called "the only live
   cell to ride on" may have concluded `cancelled` with its build cell cancelled — so
   there is *no cell to ride on*. `cancelled` is **not green and not red: it is no
   verdict**; it never proves an acceptance criterion and never disproves one. Report it
   in its own bucket; never tick against it and never hold it as a failure.
3. **Check the true head for a fresh trigger** (`…/runs?head_sha=<live-head>`); a pending
   producer that has not dispatched a cell yet provides no evidence either.

Consequence: if the only runs that could prove a runtime criterion are cancelled, **no
tick is owed** — the criterion stays unticked with a structural reason ("no completed
cell at any head"), which is the honest hold, not a defect to route around.

**A run a dispatch calls `pending`/`in_progress` is a snapshot too — it may have CONCLUDED (and concluded FAILURE) between their read and yours, and the conclusion governs the gate, not the dispatch's "once it goes green" plan.** Before planning anything on a named run, re-read `gh api …/runs/<id> --jq '{status,conclusion}'` and, if it concluded, attribute the failing STEP from that job's own log (`gh api …/jobs/<job-id> --jq '.steps[]|select(.conclusion=="failure")'`). Then say plainly that the promised write-back is **not owed** — its precondition never held — record the corrective on the PR (where the work lives), and report the correction to the dispatcher. A dispatch's conditional ("when X concludes green the only gate is Y") is void the moment X concludes red; acting on the antecedent without re-reading it is how a reviewer chases a gate that is already closed.

**Why it bites:** a stale live-cell claim invites you to (a) tick a criterion against a
run that never concluded, or (b) hold it as a hard failure when the run merely died. Both
fabricate a verdict from a cell that executed nothing. The wire read — every job's
`conclusion`, at the live head — is what separates "green", "red", and "never ran".

## Runtime-verification hold vs `## Not covered` — an in-scope criterion missing only a completed cell is a HOLD, never a Not-covered exemption

When a criterion is genuinely in scope for the PR (the code/behaviour is in the diff)
but its only missing evidence is a *completed* runtime run (a build/publish cell that has
not concluded, or only ran as `push=false` when the criterion needs `push=true`), that is
the **runtime-verification class**: hold it unticked with the structural reason, post-merge
(or post-trigger) provable. Do **not** add a `## Not covered #<n>` line to exempt it.

`## Not covered` asserts the PR does not deliver the criterion at all; using it for work
the PR *does* carry but has not yet proven at runtime fabricates an exemption for delivered
work and lifts the gate on an unverified behaviour. The gate red on an in-scope-but-
unproven criterion is the honest hold — the same distinction as the exemption-matcher note
below: "out of scope" in a dispatch is not the same as "exempted by the gate", and
"cannot prove it now" is not "not covered" either. Triggering the missing cell (e.g. a
`push=true` `workflow_dispatch`) is the implementer's lane call; when a cell concludes you
bind run id + head sha and tick.

**A criterion structurally UNOBSERVABLE in the PR's own vehicle is still a HOLD, and its
follow-up goes to the implementer — never a self-written `## Not covered`.** A trigger
workflow whose `paths` filter excludes the PR's own files cannot fire on the PR's own CI,
so its criterion ("a rebased head's trigger run reports a real guard job immediately"; "the
new head dispatches its own producer") has no evidence the PR channel can produce — even a
unit/mock test in the change set could anchor it but is absent. This is a variant of the
runtime-verification hold, not a `## Not covered` exemption: the reviewer ticks only the
criteria it can PROVE (a preserved `cancel-in-progress: false` and an untouched producer
workflow are code-provable and tick), leaves the unobservable ones `[ ]`, and routes the
follow-up to the implementer (observe on the next real rebase of a pin-bump PR — where the
new-head trigger must report a guard job and dispatch its own `push=true` producer at the
new sha — or add the unit/mock test). **When the implementer lands that unit/mock test as a new head, verify its SHAPE before flipping the structural hold to a tick: it must LOAD the real artifact the change configures (e.g. `yaml.safe_load()` the actual workflow file) and assert the invariant against the loaded object — a test that hand-copies the config constant can pass while the real workflow regresses and proves nothing. Confirm the configured artifact is byte-identical across the old→new head diff (`git diff <old> <new> -- <artifact>` empty) so the tick's code base is unchanged, run the test yourself (`pytest --noconftest -q <file>` → quote `N passed`), then re-judge each affected criterion at the new head and re-write-back the full proven set (a content move, not just a re-anchor).** The gate, run against the post-tick state, is the
evidence the tick took: the ticked item DROPS OUT of the violation set while the held ones
remain — measure it, never narrate it. Never fabricate a tick on an unprovable box and
never write the `## Not covered` remedy yourself (remedy is strictly ADD, implementer's).

## Tick only what the PR delivers — never over-tick to a dispatch's requested N/N

An acceptance write-back ticks exactly the criteria the reviewed PR **actually
delivers**, never the count a dispatch asks for. A dispatch routinely asks for a
full tick ("tick 6/6 so the next run reaches the new step") while the PR before you
implements only a subset of the linked issue — e.g. it adds the PR-body gate but
carries no change to the refiner / issue-side module the issue also requires. Some
of the issue's criteria then belong to a *different* vehicle (a fleet rollout under
another lane, a follow-up PR). Ticking them here fabricates proof for work that does
not exist.

Procedure:

1. Enumerate the linked issue's criteria (`gh issue view <n> --json body`).
2. For each, classify against **this PR's diff**, not the issue's prose: delivered
   (the file/behaviour is in the diff, with a test or gate you can cite), or not
   delivered (no change in the PR, or explicitly `## Not covered` and out of scope).
3. Tick only the delivered subset. `acceptance_writeback writeback --proven <spec>`
   accepts a comma list (`2,4,6`) or a range (`1..6`); the point is to name **only**
   the proven ones — never `--proven 1..6` when 1/3/5 are undelivered. Dry-run with
   `--dry` first, then live, then verify `gh issue view <n>` shows those boxes `- [x]`
   and the rest still `- [ ]`.
4. Report the divergence to the dispatcher: the verdict is the honest subset, the
   remaining criteria stay unticked, and the gate that reads them will **still
   hold** the gate-PR until those other vehicles land. That hold is the designed
   behaviour, not a defect to route around by over-ticking.

**Why it bites:** an over-ticked box is a claim a reviewer certified proof that no
diff supports. The next reader trusts the ticked issue, the shield lifts, and the
undelivered criterion ships unverified. The gate reading the issue is *correct* to
stay red on the unproven criteria — that red is the whole reason the write-back must
stay honest. Name the failing/unproven criterion, the head sha and the run id in the
verdict and the report; never present a fabricated 6/6 as a completed review.

**Read the BOX, not the `unproven:` summary, after a write-back.** The body's trailing
`unproven:` block is written with the LAST verdict-ref used and can carry a STALE
`comment=<id>` (e.g. a superseded re-tick) on a line whose checkbox is already `- [ ]`.
A peer re-reading the summary will then report "your re-tick did not land" when the box
is actually blank-and-correct. The checkbox lines are authoritative; the `unproven:`
summary is a cosmetic remnant. After any un-tick/re-tick, verify state via the box lines
(`grep -E '^\- \[.\]'` on the body), and when a stale citation is confusing a peer, state
plainly that the box already reflects the current disposition instead of re-running the
write-back to scrub cosmetics (re-running churns a closed issue for nothing).

Also note the `check-pr-acceptance` gate's exemption matcher is narrow: it exempts an
unticked criterion only when the PR body names it under `## Not covered` with a linked
`#<n>`, matched on the criterion's **first three words**. A criterion the PR genuinely
does not deliver but does not restate verbatim in `## Not covered` therefore still
reds — so "out of scope" in the dispatch is not the same as "exempted by the gate",
and you cannot rely on it to clear the box-PR.

## A proof-by-run witness sweep: verify its SHAPE (the cpu-only cell present, the GPU cells absent) while it is in_progress, but TICK only on the run's all-success conclusion

When a runtime criterion (e.g. "default `make engine-build` sweep is green **without** the vllm GPU cells") is gated on a dispatched default sweep, the run is evidence in TWO separable facts:

1. **Shape** — readable as soon as the run has jobs: does it contain `engine-build-vllm-cpu` (success or in_progress) and **no** `engine-build-vllm-cuda` / `engine-build-vllm-rocm` cells? Presence of the cpu cell and absence of both GPU cells IS the `DEFAULT_CPU_ONLY={"vllm"}` configuration the criterion's "without the GPU cells" clause demands. That shape is durable evidence the moment the job list materializes — post it as a load-bearing on-wire comment (`gh api .../issues/<n>/comments`) so the shape half is not lost if the later all-green run's jobs list rotates away.
2. **Conclusion** — the criterion says "green": provable ONLY when the run-overall concludes all-success. A populated job list with the cpu cell SUCCESS while OTHER non-vllm cells (tensorrt, strata, sglang...) still run is **in_progress = NO VERDICT** for the sweep. Never tick the criterion off a cell-level cpu success; the run object's own `conclusion:null, status:in_progress` is the gate.

So: verify AND post the shape now; hold the tick until `.../actions/runs/<id>` returns a non-null conclusion. A post-tick gate run (or fresh guard) that drops the criterion out of the violation set is the authoritative on-wire proof — measure that, never narrate it.

**The `- unproven: N. <ac text>` line under an open box is the acceptance_writeback tool's OWN authoritative "not proven" marker for a held AC — it is load-bearing, NOT garbage.** A peer who spots it and calls it "a dropped/malformed jq fragment" is misreading a deliberate render (often conflating it with a REAL fragment injected by an earlier malformed first-attempt write-back). Verify with a deterministic grep: if `select\(\\.user.login` and `unexpected token` both return 0 matches while `- unproven: N\.` returns 1, there is NO fragment — the unproven line is the tool's record that AC N is proven-side-absent (AC4 held as proof-by-run renders exactly this). NEVER strip it and NEVER authorize a peer to strip it; stripping erases the write-back's "not proven" record and a future write-back/gate reads that line's shape. Decline the peer's hygiene offer, name what the line IS, and restate the correct post-write-back state.

**A verdict-gated tick can CLEAR `check-pr-acceptance` and thereby UNMASK a `check-pr-base` (#845) red the dispatch's gate list never carried.** The acceptance gate sits early in the guard chain; when your `--proven` write-back ticks the linked issue's boxes, the re-run concludes the acceptance step SUCCESS and the job proceeds to the NEXT gate, which had been red underneath all along (or flips red the moment a sibling merge advances `origin/main` past the PR's base). The gate's own stdout is the adjudication — run it yourself: `python3 scripts/check_pr_base.py check`. Typical output: `check-pr-base FAILED: merge-base(origin/main, HEAD) = 24a4abeef…, not refs/remotes/origin/main itself` + a "foreign commits" list + "rebase onto a fresh refs/remotes/origin/main". This is a BASE-DECISION, not a code-verdict issue and NOT your rebase to perform: per #1015 a rebase fires only on an actually CONFLICTING board state. Route it to the planner/merge-conflict lane, say plainly you did not rebase/push/arm, and note the verdict + acceptance tick stand at the graded head even though the guard shows a new red from a gate after acceptance in the chain.

## `check-pr-openspec-change` reds on an `agents/`-skill-only pointer vehicle — and the guard chain may SKIP it (short-circuit), hiding it until you run the gate yourself

The `agents/` docs-only exemption in scripts/check_pr_hygiene.py's `_is_docs_only` covers CHANGES.md, README.md, `docs/`, and `agent-wiki/` but NOT `agents/` skill paths. A pointer-in-skill vehicle (a #1849-lane rollout: adds `agents/<lane>/skills/…/SKILL.md` block + a new `references/*.md` + change-note trio, no `openspec/changes/` dir, body names no `OPENSPEC: <name>`) therefore counts as "changes product code" and `make check-pr-openspec-change` FAILS rc=1 with "adds no file under `openspec/changes/` and names no existing change".

Trap: in the guard job the openspec-change step sits AFTER `check-pr-acceptance`; on a lane vehicle whose AC self-red keeps `check-pr-acceptance` red, the openspec-change step is **skipped** (short-circuit), so neither the CI run nor a verdict that ran only check-docs/lint/check-agent-skills ever surfaces it. Run `python3 scripts/check_pr_hygiene.py openspec-change --root <repo> --head HEAD --base <base> --body-file <live-body>` DIRECTLY on every `agents/`-touching vehicle before claiming "all gates pass" — treat a clean local trio as insufficient evidence until this one is explicitly green. It is a real diff-shape gate (NOT AC, NOT base), NOT satisfied by any acceptance write-back; remedy is the owner/implementer's (add an `OPENSPEC: <name>` body line naming the active #1791-class change, or an `openspec/changes/<name>/` dir). Report it on the PR with the exact rc=1 finding for BOTH the current vehicle and any sibling vehicles (same root).

## Criterion text can name a doc file the repo does not maintain — resolve against the repo's own of-record source

An acceptance criterion can name a doc-of-record file the repo does not actually use,
and holding on its literal absence over-restricts a delivered change. A criterion can
say "change-note: `agent-wiki/…` + `docs/changes.d/…` row + `docs/BOTS.md` row" while
the repo's change-note mechanism is only the first two plus the rendered `CHANGES.md`.
Resolve by reading the repo's OWN stated mechanism, not the criterion's prose: if the
named file's own intro says the per-change record lives elsewhere (BOTS.md declares
itself a prose bot/CI reference — "each change's own record is a dated note in
`agent-wiki/` with its own row under `docs/changes.d/` … rendered into `CHANGES.md`"),
then a missing row in *that* file is a criterion-naming artifact, not a missing
deliverable, and the criterion ticks on the of-record trio being present.

**Procedure:** before holding (or ticking) a criterion on a doc-marker, read the repo's
own stated of-record convention (the doc file's own intro, `make changes-index`,
CHANGES.md) and decide whether the named file is actually a per-change changelog in
this tree. A peer's tree-proof proposing a tick you held for a literal absent file
should be checked against that mechanism, not re-litigated against the criterion's prose.

**Distinguish the change-note for THIS fold from superseded history entries.** When a
doc-gap criterion is filed on "the note documents a superseded value", enumerate ALL
dated notes matching the scope before claiming the gap: the fold has one current
change-note (a correctly-dated file spelling the resolved value verbatim) plus older
history entries that documented earlier pending/ruled-out values. Crediting a history
entry as "THE change-note" produces a false gap; the current change-note may coexist
with the superseded one and is the one the criterion binds to. **Distinguish the mandated-rebase case from the never-live-artifact case (both arrive as a hold, but for different reasons).** A substituted artifact documenting the resolved state is tickable under the caveat above — UNLESS the exact artifact named by the criterion (its literal filename) is genuinely available one *mandated* rebase away: the owner's standing directive to rebase the open PR onto latest main pulls the exact-named files (e.g. a merged PR shipped `2026-11-03-…` to main) into the head. When that is true, do NOT settle for the substitution — HOLD the tick until the rebase lands, then tick the exact-named files at the NEW head. Same `[ ]` state as a doc-gap hold, but the remedy is the rebase (implementer/owner lane), not a docs edit; report the condition openly so the board knows the hold clears on the rebase, and re-check at the new head rather than re-binding to the substitute. The distinction is the *remedy*: a doc-gap hold clears on a docs edit, a rebase-hold clears on the rebase — name which one it is so the board routes the hold to the right lane.

**Caveat — a SUBSTITUTED of-record artifact only ticks if it documents the RESOLVED state, not a superseded value.** Resolving a criterion-naming artifact against the repo's own mechanism does not license ticking on *any* surviving change-note. Check the substituted file's CONTENT against what the head actually ships: if the head's resolved value is one thing (say the fold ships `360`) but the substitute note documents an earlier, later-superseded figure (say `240 → 480`), the documentation CONTRADICTS the shipped state and the criterion is genuinely unmet — that is a real docs gap, not a naming artifact. Procedure on a peer flag of an over-tick (even against your own latest tick; the write-back seam makes the box yours to correct):

1. **Un-tick** the box via the acceptance write-back limited to the positions you are KEEPING (`--proven <kept-positions-only>`); every position not listed renders `- [ ]`. Verify on-wire that the kept boxes stay `[x]` and the flagged box is `[ ]`.
2. **File the missing/mismatched note** as a tracked OPEN work item naming the exact correction (the note must document the resolved value verbatim), so the gap has a home and the tag can be removed when it lands.
3. **Post the correction verdict on the PR**, not the issue, so the board shows the reconcile; then report both the un-tick and the tracked issue back to the dispatcher.

**Lesson (corrected a false gap):** before declaring a change-note criterion unmet because the substitute documents a superseded value, ENUMERATE every change-note in the base AND branch (`git ls-tree -r --name-only <base> | grep -E 'agent-wiki|changes.d'`), not just the one matching the criterion's filename. A correct-value note under a different date (e.g. `2026-11-06-engine-build-matrix-timeout.md` documenting the resolved `360||240` fold verbatim, measured-band sized, naming the issue's criterion as its tracked item) satisfies the tick even though the criterion text names `2026-11-03`. A date/name substitution carrying the RESOLVED value is proof, not a gap — only a note documenting a SUPERSEDED value is a gap. When you unfind a gap you yourself filed, say so plainly and re-close it: re-tick the box `--proven <kept+restored>`, update the tracked issue (close it if the exact named files merged elsewhere), and post the correction on the PR citing the resolved-value note. The wire shows the correction as a retraction, which is the only non-fabricated way to end a false gap.

## A render/`apply` mode that writes to stdout does not modify its input file

Before verifying a re-render, know which mode you are in. A `--apply` / render subcommand that
ends in `sys.stdout.write(out)` (or simply prints the new body) leaves the input file untouched —
so grepping the input file for the new sha returns the OLD one and reads as "apply preserved the
stale pins". Redirect the render to a file and grep THAT:

```
python3 <tool>.py apply --body live.md > rendered.md     # not: apply --body live.md
grep -c '<new-sha>' rendered.md ; grep -c '<old-sha>' rendered.md
```

Assert on the rendered body first (new-sha count N, old-sha count 0, marker/box counts
unchanged), then PATCH the rendered file onto the wire. Only the PATCH moves text; the render
mode moving nothing is the expected behaviour, not a bug to work around by editing the input.

## A head adopting the base's resolved value can still satisfy a tick — read the criterion's text, not the branch's historical delta

A head move can REPLACE the value a criterion was ticked against — e.g. a branch that raised a matrix cell cap to `480` is reforked onto main, and the new head adopts **main's own** value (`360 || 240`, byte-identical to base) with the branch's distinguishing `480` simply gone. The impulse is to hold the pre-existing tick as stale because "the branch's value is no longer there". That is judging the tick against the branch's historical delta, not against the criterion.

Read the criterion's own verbatim text first. If it says "heavy GPU/rocm cells at **~360 min**, cheap cells unchanged at 240 (a matrix column)", the resolved `360` satisfies it **exactly** — the criterion never demanded the branch's `480`. The tick STANDS, re-anchored to the new head.

**Procedure on any head-move where a polled-fold/workflow value changes:** diff only the moving files, then re-read the linked criterion's verbatim text and judge the tick against THAT, not against the value the branch first proposed. A fold resolved to a different (even base-identical) value that still satisfies the criterion keeps the box green; only a value that falls OUTSIDE the criterion's own band loses it. Note in the write-back that the branch's original distinguishing value is no longer present — it matters for the owner's downstream ruling scope even when the tick survives.

## Re-anchoring box citations after a head move must be verified with a gate run made AFTER the PATCH

When the head moves and you re-anchor the ticked boxes' citations to the new sha (a `verdict-ref` rewrite of `head=`/`run=` only, marks untouched), the run id you naturally cite is the guard run measured **at that head** — but that run was created *before* your `acceptance_writeback` PATCH. It proves the pre-patch state, not that your PATCH left the gate clean. A citation rewrite is a regex-sensitive edit: a malformed `head=`/`run=` field, or a stray reflow, can silently stop a box from parsing and REGRESS the gate (4 violations → 5).

So after any re-anchor PATCH:

1. **Re-run the real gate against the live bodies** — fetch the PR body fresh (`gh api …/pulls/<n> --jq .body`) and run `check_pr_acceptance.py check --body-file <that>`; do NOT rely on the cited run. (The `check` subcommand takes only `--body-file`/`--body` — there is no `--head`: passing a sha errors `unrecognized arguments` and the gate never runs. It reads the body you hand it, so fetch the live body first, then point `--body-file` at it.) Require the violation count to equal the held set, unchanged from before the PATCH.
2. **Census the boxes on-wire** — every ticked box still `- [x]`, every held box still `- [ ]`, and the stale old sha count in each issue body is `0`.
3. **Post a short follow-up comment on the PR** when the verdict/COMMENTED review was posted BEFORE the re-anchor: the review text predates the mutation, so the thread's stated basis no longer matches the wire. The follow-up names the new citation (`comment=… head=… run=…`), confirms marks unchanged, and states the gate re-read at that head. One follow-up, not a second verdict.

**Why it bites:** the cited run and the PATCH are two different moments; treating "a green run at this sha exists" as "my citation edit is sound" is precisely the assumption a regex edit breaks. The post-PATCH live gate read is the only thing that proves the re-anchor did not corrupt the record.

**A run created before the PATCH is not automatically stale — its CONCLUSION is what binds, and a run still in flight at PATCH time that later concludes SUCCESS at the same sha proves the post-PATCH tree.** The rule that a pre-PATCH run "proves the pre-patch state" applies to a run already CONCLUDED when you PATCH. A run that was still `in_progress` when the PATCH landed and finishes afterwards has read the post-PATCH world; poll it to `completed` and, when it is `success` at the graded head, post it as the CI-clearance record (run id + head sha + the per-job conclusion list). Re-read the run before reporting — `in_progress` is no verdict and must never be quoted as "green, pending confirmation".

**Distinguish a TICK PATCH from a re-anchor PATCH in the post-PATCH gate expectation.** A re-anchor
(marks untouched) must leave the violation count UNCHANGED. A genuine **tick** must do the opposite:
the count must DROP by exactly the number of newly ticked criteria, and each newly ticked criterion
must be ABSENT from the violation list. Re-run `check_pr_acceptance.py check` on a freshly fetched
body (`gh api …/pulls/<n> --jq .body`) and assert both — e.g. 5 violations → 4 with the ticked item
gone from the list confirms the tick functionally landed, not merely that the body shows `- [x]`. A
tick whose count did not move (or whose item still reds) did not take (wrong criterion index, or
criterion text that does not match the issue) — re-read the box line and the gate, and do NOT report
it landed.

**Verify a peer's named "completed run id" by DIRECT run read before binding — a 404 proves nothing.** A dispatcher relaying "a completed producer run id X fired at the head" may be citing an id that does not exist (HTTP 404/Not Found on `gh api …/actions/runs/<id>`); a pending pr-trigger run and a phantom 404 must not be conflated. Before any runtime tick that names a run, read the live run back: `gh api …/actions/runs/<id> --jq '{id,head_sha,status,conclusion}'`. If it 404s, say so plainly and bind to NO runtime criterion until a GENUINE completed run exists at the head; never tick a runtime criterion off a run id you cannot read, and never reuse the pre-rebase witness after the rebase (the head moved — re-bind at the NEW head, never the old ea0b9033-era witness, never a 404 id).

## A pending pr-trigger with frozen updated_at and NO job may be the DESIGNED concurrency-queue signature, not a stuck scheduler

A `pull_request` pin-bump trigger shows `status: pending`, `updated_at == run_started_at`, and a **404/empty `/jobs`** (the run record exists but its `trigger` job is not yet created) for HOURS while another engine-build producer cell is in flight. That signature is the trigger waiting **behind #917's global `engine-build-push` concurrency group** — it is *designed*, not a defect. It will not "dispatch its own producer" until the queued run's job gets a runner, and nothing about the frozen timestamp means it broke.

Do NOT report a pending trigger of this shape as "stuck/genuinely broken" until you have checked whether an in-flight producer of the same selection already holds the queue's slot: read `…/runs/<id>/jobs` (404/[] while queued) AND the producer board (`…/actions/runs?event=workflow_dispatch&per_page=30`) for an in_progress cell. If an in_progress cell exists, the trigger is concurrency-queued, plain waiting — re-arm the watcher on the producer CELL (job name, e.g. `engine-build-vllm-rocm`), never on the trigger; the trigger's dispatch is a non-event by design until the queue drains.

**Why it bites:** misreading the queueing signature as a scheduler defect leads you to demand a re-dispatch of a producer that already holds the slot, churning the build the queue is correctly waiting on — the exact "never cancel/never churn a live run" failure.

When the blocking criterion is a runtime run at a params-equivalent old-head that may conclude SUCCESS, the reviewer's watcher exits to SAY the cell concluded (status+conclusion+run id+head), and STOPS there. It never announces "the criterion is ticked" / "bind satisfied" on its own: whether a params-identical old-head cell satisfies a runtime bind whose text demands the CURRENT head is an adjudication for the dispatch-seam owner (pipeline lane) / planner, precisely because the criterion may name a head the run does not carry. The reviewer's evidence is the empty params diff + the concluded run; the ruling is the owning lane's. Re-arm on the real producer cell or a new-head run, never on a queue-held trigger.



## The run payload exposes NO dispatch inputs — prove an engine-build run's arch/push by its JOB CELL name, never by assumption

A `workflow_dispatch` engine-build run created on the right branch/head is NOT by itself evidence it ran (or will run) the arch a criterion demands. `gh api …/actions/runs/<id>` does not reliably return `inputs` (usually `{}`), and a `pending` run has zero jobs — so you cannot tell `arch=cuda push=false` from `arch=rocm push=true` from the run record alone. A new-head run whose intended arch the dispatcher stated in prose is still unproven until:

1. it spawns a job cell whose NAME carries the arch (`engine-build-vllm-rocm` vs `-cuda`), and/or
2. its `concurrency.group` key (pull from the run or job logs) shows the push flag (`…-push` vs `…-build`), and/or
3. an implementer dispatch bookend comment quotes `engine=vllm arch=… push=…`.

Credit the run to an AC only after the cell NAME proves the arch and, where the criterion needs `push=true`, the push flag is proven. A `cuda` cell conclusion satisfies no `rocm` criterion (a cuda-fed rocm tick is a FALSE write-back — one lane corrected an over-claim exactly this way); a `push=false` verify satisfies no `push=true` publish criterion. When a rebase supersedes the head a run was dispatched at, that run's evidence binds a dead head and is worth nothing at the new head — the fresh post-rebase runs are the channel.

- The **PR/issue thread** is where a single PR's disposition lives (verdict comment,
  seam tick, correction).

**When the PR head REBASES after the write-back, it is a content move to a new head — re-judge and re-anchor, never claim the ticks survive on the old sha.** A rebase onto latest main de-parents the graded sha (old is not an ancestor of new) and the tree differs by whatever main moved (e.g. sets of newly-merged PR files). Do NOT treat it as a landing-squash (byte-identical) or as re-verdict work — instead: (1) check the fix's own symbols/tests exist at the new head, (2) re-run the relevant test at the new head yourself, (3) re-run the write-back with `head=<new> run=<new-guard-run>` to re-anchor (marks unchanged), and (4) post a short re-anchor note on the PR naming old→new and quoting the re-run. The acceptance_writeback re-render PRESERVES whatever prose is in the body, so if an earlier attempt injected garbage into the AC section, sanitize the body surgically before/while re-anchoring (build the clean body, assert the box count and each citation, PATCH once, then re-read live). Never leave `head=<stale>` on a ticked box after the head moved; the wire must carry the graded head.

**`gh api -X PATCH -F 'body=@<file>'` requires the file to exist at PATCH time — and a sanitize script that DRY-Writes to a temp path only materializes if the writer itself succeeds.** Sequence the PATCH after the file is actually written and confirmed (`ls -la`), never in the same batch as the writer that may still fail.

**Post-PATCH the write-back regenerates the marks from the CURRENT body — a malformed verdict-ref on the FIRST attempt injects prose into subsequent renders.** If the comment-id variable fails to parse on the first `--proven` PATCH, the raw jq error line is embedded verbatim into the box section; the corrected re-render rewrites each box's `(proven: …)` but leaves the orphaned error fragments. Fix by sanitizing the issue body (strip exactly those garbage lines) and re-PATCHing once; verify the box count and citations are unchanged on the read-back. Never leave a fabricated verdict-ref string in an issue body, and after a `comment=` variable has once failed, pin the id from the POST's printed response rather than a live `.[-1]`/descending read.
- The **reusable rule** lives here (this skill's references).
- **Persistent memory** holds cross-session facts (who the user is, environment, standing
  conventions) — never a transient per-PR resolution. Writing a resolved PR's verdict
  ids into memory burns a hard budget on a fact that is stale in days.
