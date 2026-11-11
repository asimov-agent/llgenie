# check-pr-closing gate (a claim needs an adjacent close, in BOTH body and squash text)

> See-also `finding-close-and-merge-state.md` — when a `closes` is LEGITIMATE (never on a
> docs-only record PR over an unfixed finding), closing an already-landed OPEN issue, and
> reading auto-merge state across BOTH REST and GraphQL.

A PR body that references its issue as a claim — `Issue: #N`, or a subject ending
`(#N)` — is NOT a close. The `guard` job's `make check-pr-closing` (#1417/#1418)
reds until the SAME issue is closed adjacently (`closes #N`) in **both** the PR
body and the **squash commit message**. A lane can rebase onto a clean base and
still see `guard` red purely because the squash text ends `(#N)` with no adjacent
`closes #N`.

**Read the WHOLE commit message, not just the subject line — the close usually lives in the
message BODY, and a subject-only read manufactures a false red.** Diagnosis that cost a
false-positive flag: checking `gh api .../commits/<sha> --jq '(.commit.message|split("\n")[0])'`
across a rebased chain showed `closes=0` on every commit SUBJECT, so I flagged a missing close —
but the success guard run at that same head read `check-pr-closing=success`. The `closes #N` sits
in each commit's message BODY (below the subject), which `split("\n")[0]` discards. Always grade
against the full `.commit.message` (or, decisively, the actual `check-pr-closing` exit in the
head's guard run) before claiming the squash text lacks the close: `gh api .../commits/<sha>
--jq .commit.message` and grep the literal adjacency in the whole string.

**`**Closes:** #N` (bold, colon-suffixed) is STILL a claim, not a close.** A lane that
"fixes" a bare-body red by writing a Markdown heading line `**Closes:** #1634` reds the
gate identically — the parser wants the literal adjacent keyword form (`closes #N` /
`fixes #N` / `resolves #N`) as its own plain line, not a rendered label with a colon.
When a lane reports "body fixed and live" but the guard still prints "the PR body does not
adjacently close #N", read the actual body (`gh pr view <n> --json body`): a `**Closes:**`
label is the common false fix. And the squash text must carry the same plain adjacency —
fixing the body alone leaves the squash-text violation standing (both rows red together).

## What it looks like

- `guard` / `check-pr-closing` fails at the head; the log prints the failing
  `make check-pr-closing` step and the verbatim PR body (with the claim, e.g.
  `Issue: #1465`), so the mismatch is readable directly from the run log.
- **A generated body that names an already-CLOSED meta-issue in prose is an over-flag, not an amend.**
  Machine-generated PRs (engine-bump, registry-sync, bump templates) often write text like
  "Automated engine pin bump (issue #107)" where `#107` is a long-closed ancestor/meta issue, not
  something the PR closes. `check_pr_closing.py` reads any `#N` mention as a CLAIM and reds demanding an
  adjacent `closes #107` in BOTH the squash text and the body — which the template never emits
  (`closingIssuesReferences=[]`). Do NOT fabricate `closes #107` to satisfy it (that would claim a closure
  the PR does not perform, and #107 is already closed so nothing would auto-close). Diagnose by confirming
  the mentioned issue is `state=closed` (`gh issue view <n> --json state`) and that the mention is prose, not
  an `Issue: #N`/subject-`(#N)` claim. This is a template/gate defect owned by `llgenie-ci-pipelines-maintainer`
  (rewording the template to drop the parenthetical, or teaching the gate that a reference to a closed
  meta-issue inside a generated body is not a closure claim) — never weaken the adjacent-keyword check
  itself. Route it there; do not dispatch a fix-bot amend on the generated branch.
- One mismatch can red **several** check names at once — `scope` and one of the `guard` rows run the same `make check-pr-closing` target, and `ci-verdict` reds on the failure. A head reading `scope FAIL + guard FAIL + ci-verdict FAIL` is one defect: read the log, dispatch one amend, never one fix per red name.
- **Never name a **PR** number in the close text; lanes habitually write `(fixes #<pr>, #<issue>)` where the first id is the PR itself. The gate and the convention both want issue numbers only.
- This is a **PR-content / commit-message** defect, not a stale-base or
  rebase defect — verify by reading the failing job's log at the exact head, not
  by assuming the rebase did not take. **COUNTERTYPE — the event-frozen-base red.**
  A lane CAN see `check-pr-closing` red with a *correct* commit-message and body
  when the run evaluated an event-frozen `--base <pre-merge-sha>`: a PR merged onto
  main AFTER that base sha entered the checked commit range, so the gate's
  violations all name the *merged* PR's squash ("claim #X … adjacently close #X",
  "body must close #X", "the joined commits close A, B; the body closes A — sets
  must be the same") even though neither the branch nor its author claim X. This is
  NOT an amend owed — adding `closes #X` would be fabrication. It is a gate defect
  owned by ci-pipelines; the per-PR remedy is a **rebase onto current origin/main**
  to refresh base.sha and collapse the range to the branch's own commits.
  Distinguish the two by the log: an amend treats the body/commit text the PR
  itself carries; the stale-base red quotes violations about a PR *outside* the
  branch. When a rebase is owed (fresh base) it is permitted regardless of the
  clean-head rule; a head red on this defect is a rebase owed, not a clean head.
  **The countertype is FIXED in-tree (#1527 by PR #1534):** the workflows now pass
  `PR_BASE: origin/main` plus a fresh `git fetch --no-tags --prune origin main`,
  and `check_pr_closing.py` anchors at `git merge-base origin/main HEAD` instead
  of the event-frozen `base.sha`. A stale-base red after that merge means the gate
  regressed or the base sha is still frozen somewhere — file it to ci-pipelines,
  do not dispatch rebases in a loop. A red on the checked PR's OWN commits is
  always an amend, never a rebase.
- **"The joined commits close (none); the body closes #N" on the PR's OWN range — the
  COMMIT messages are the defect, not the body.** The gate requires the squash-commit
  closing set to EQUAL the body's closing set (the squash body is what `git log` keeps;
  the PR body is what GitHub auto-closes from). When the body ALREADY carries a legitimate
  `closes #N` for the PR's own issue but the joined branch commits close none, the body is
  correct and the fix is to make a commit message carry the closing keyword for #N
  (amend/squash, force-with-lease). Do NOT tell the lane to "fix the body" — that is a
  self-misdirection that leaves the red identical on the next push. Read BOTH sides before
  routing: `gh pr view <n> --json body` (does the body close #N?) and the branch log
  (`git -C <tree> log --format=%B origin/main..HEAD`, or the commits the log prints). This is
  the SAME "sets must be the same" wording as the stale-base countertype above — tell them
  apart by WHOSE issue is named: the stale-base red names issues OUTSIDE the branch; this one
  names the branch's own issue with the body side already correct.
- **The MIRROR of the above — commit subject closes #N, body closes (none): the BODY is the
  defect, not the commit.** Same "sets must be the same" rule, opposite side. A subject ending
  `(closes #N)` (which `git log` keeps as the squash text) with a body that only mentions the
  issue in prose `(#N)` — no literal `closes #N` line — prints "The joined commit messages close
  #N. The pull request body closes (none)." The commit is correct; add the plain adjacent
  `closes #N` line to the body and leave the commit alone (do NOT re-author the commit, and do NOT
  "fix" the subject down to `(#N)` — that moves the violation to the squash-text side). Diagnose
  BOTH: `gh pr view <n> --json body` (does the body carry a literal `closes #N` line, not just
  `(#N)` in prose?) and the commit headline. Literal adjacency in one place and prose in the other
  is the red; the remedy is one plain line on the missing side.
- **The PR body printed in the job log is NOT guaranteed to be the body of the PR whose checks you are
  reading.** A `guard`/`scope` run attached to PR X (it appears in `gh pr checks X`) can evaluate with
  `PR_BODY` env holding a *different* PR's body — the log then reds X while quoting claim text that belongs
  elsewhere. Before quoting the printed body as evidence or dispatching an amend, compare it with the PR's
  own body: `gh pr view <n> --json body`. Two independent facts, both need checking: (a) does the PR's OWN
  body claim the issue without an adjacent `closes #N`? (that amend is owed regardless), and (b) did the
  failing run evaluate the wrong body? (that is a workflow-robustness finding — report it to ci-pipelines;
  never self-fix a CI script from this lane and never let the misattributed log dissuade you from the
  amend the PR's own body requires).
- **A red on a body the lane ALREADY fixed is a STALE-BODY read, not a continuing defect — but a rerun does
  NOT reliably clear it; a fresh head does.** `PR_BODY` is populated from the run's own trigger payload
  (`github.event.pull_request.body` captured at push time), so the gate evaluates the body as it was when
  that event fired, not the body typed a minute later. Diagnose first: (a) fetch the CURRENT body
  (`gh pr view <n> --json body`) — if it opens with a plain `closes #N`, the fix is already present in the
  tree; (b) compare the failing run's `created_at` against the push/body-edit timeline
  (`gh api repos/<o>/<r>/issues/<n>/timeline` — `head_ref_force_pushed` and body-edit ordering). If the body
  now carries the close but the run predates the edit, `gh run rerun <run_id> --failed` is permitted (it is
  a concluded run, not a live one, not a merge, not an arm) — but treat it as a cheap first try, never the
  fix. **Measured counter:** a rerun re-executes the SAME run and therefore the SAME event payload, so it
  kept redding identically through attempt 3 on a body the PR already carried correctly; the green only
  arrived when the author pushed a NEW head, whose push event repopulated `PR_BODY` from the corrected body.
  So when a rerun reds identically and the local gate says OK, stop rerunning: have the author push (the
  commit-message side owes the squash-text close anyway) and do not relabel the residual as infra — it is
  a stale-payload artefact of that run, and the remedy is a new head.
  **Discriminator — ask WHAT the gate reads before deciding "rerun helps" or "only a new head helps".**
  `check-pr-closing` reads `PR_BODY` out of the run's event payload, so a rerun replays the same frozen
  text and a new head is the only cure. A gate that re-fetches live state over the API at run start (e.g.
  `check-pr-acceptance` reading the ISSUE's `## Acceptance criteria` box state) is NOT event-frozen: the new
  attempt sees the ticks written after attempt 1 started, and a rerun DOES clear it. So the same visible
  shape — "only step `make check-pr-X` red at a head where the underlying object is already correct" — splits
  into two opposite remedies by one question: is the graded text in the event payload (push a new head) or
  re-read live (rerun the concluded run)? Emit the answer with it: post the failing step, the run's
  `created_at` and the write-back's timestamp, then dispatch the lane that owns the remedy and confirm it
  landed by `run_attempt` incrementing on the SAME run id (a rerun creates no new run object) plus the
  previously-failing step reading `completed/success` in the new attempt — not by "I dispatched it".
- **When the body is the graded input, dispatch "push a NEW head", not "re-run" — never promise a rerun
  re-reads an edited body.** `check-pr-closing` and `check-pr-acceptance` both take the PR body from the
  run's own trigger payload, so a rerun replays the text captured at the original push; a lane told "just
  re-run CI, it will re-read your fixed body" will burn a run and report the same red. Say instead: an
  empty commit or any push re-fires the event with the corrected body, and that is the reliable cure. A
  rerun is only a cheap first try, and only for a step that re-fetches its graded object live over the API
  (an issue's checkbox state, a label, a merge state) — check which side the failing step grades before
  naming the remedy, and state the mechanism in the dispatch so the lane does not treat the repeat red as
  a new defect on its fixed body.

## The mirror case: a diff that satisfies an OPEN parent issue's acceptance but the body closes only one

Before treating a PR's close set as complete, read the PR's DIFF against the other OPEN issues it is
related to — not only its body. A fix issue is frequently the *parent* (its acceptance criteria are the
guard the symptom issue complains about), and one change can satisfy both: e.g. a pagination hotfix
whose new helper both walks every page AND still raises the parent's "truncated listing cannot be a
verdict" error when `total_count` exceeds what was returned implements the parent's criteria verbatim,
while the body says only `closes <symptom>`. Merging then closes the symptom and **strands the parent
open with no vehicle** — the worst outcome, because it looks tracked while nothing will touch it.

Check: `gh issue view <parent> --json state,body` (OPEN?), then read the PR's patch for the parent's
acceptance wording (`gh api repos/<o>/<r>/pulls/<n>/files --jq '.[]|select(.filename=="<file>")|.patch'`).
If the diff genuinely satisfies the parent, tell the author to add `closes <parent>` to BOTH the body
and the squash text (same set the gate enforces) — or, if only partially served, say so explicitly on
the issue so the parent's remaining scope is recorded. This is the mirror of the vacuous-close case
below; both are the same rule (the close set must be ACCURATE — nothing stranded, nothing vacuously
closed), and neither is a reason to close the PR.

## `closes #N` where #N is already CLOSED is a vacuous close set — correct it before merge

A follow-up/hotfix PR that re-does work for an already-merged issue often carries `closes #N` where `#N` is
`COMPLETED` (its original fix landed via another PR). The gate passes — the keyword and issue are adjacent —
but the close set is empty in effect: the merge closes nothing, and the squash body on `main` will assert a
closure that already happened, mis-attributing the repair. Before treating such a PR as merge-ready, check
`gh issue view <n> --json state`; if it is already closed, have the author retarget the reference to the PR
whose gap is actually being repaired (e.g. "follow-up to #<merged-pr>") and drop `closes #N`, keeping the
close-set accurate per the same rule the gate enforces. This is a body/squash-text edit on one vehicle, not
a reason to close the PR — the work itself can be entirely correct.

## A multi-vehicle rollout's umbrella tracker: NO single vehicle may auto-close it

When one tracker issue is implemented by N lane PRs (each slice its own vehicle), the
tracker must stay OPEN until every vehicle merges AND the tracker's `## Acceptance
criteria` are ticked. A vehicle whose body legitimately carried `closes #<tracker>`
("this slice completes the tracker") propagates that keyword into its SQUASH message, so
GitHub auto-closes the umbrella the instant that ONE vehicle merges — while sibling
vehicles are still open and the criteria read 0/N ticked. The tracker then looks done on
the board while two-thirds of the rollout is unmerged.

- **Check the tracker after EVERY vehicle merge**, not just its own PR:
  `gh issue view <tracker> --json state,stateReason,closedAt,body`. If `state=CLOSED`
  while acceptance boxes are unticked or other lane PRs for it remain open, the closure
  is premature.
- **Remedy is a planner board act, not a PR edit:** `gh issue reopen <tracker>`, then post
  ONE comment naming the auto-closing merge sha, the ticked count, and the still-open
  vehicles. Never reopen the vehicle PR (its diff is now main's) and never "fix" the
  vehicle body retroactively — the squash already landed.
- **Prevent it on the vehicle:** a slice's body/commit must scope to its own work
  (`part of #<tracker>`, `does not close #<tracker>`) and must NOT carry an adjacent
  auto-close keyword to the umbrella. A lane body that says its single-slice change
  "did close the tracker's implemented vehicle" is exactly the trap.
- **Distinguish from the legitimate parent-close** (the mirror case above): there the
  closed issue is a *narrow* fix that one PR genuinely satisfies; here the closed issue is
  the *multi-vehicle umbrella*, and closing it strands open vehicles plus unticked criteria.
  Same close-set-accuracy rule (nothing stranded, nothing over-closed), opposite direction.
- **The same `closes #<tracker>` on a slice ALSO reds `check-pr-acceptance`, and that is the
  faster discriminator.** A slice body closing the umbrella makes the acceptance gate read the
  umbrella's `## Acceptance criteria` (all `- [ ]` mid-rollout) and print one violation per
  unticked criterion — while a sibling slice that only REFERENCES the tracker ("part of #N", no
  adjacent keyword) passes `scope` cleanly. So when two sibling vehicles show opposite `scope`
  verdicts on the same tracker, diff their BODIES for a close keyword before assuming a gate or
  payload defect: the closing one is the defect, the referencing one is the proven pattern. The
  remedy is a body edit (drop `closes #<tracker>`, keep the reference) — never ticking the
  umbrella's boxes from a lane to silence it, and never a rebase (a checkbox cannot be rebased
  away; confirm `base == origin/main` first).

### The FINAL vehicle of a rollout tracker can never go green pre-merge — a state criterion is not a defect

A tracker's `## Acceptance criteria` often ends with a *state* criterion describing the rollout itself ("the
three PRs merge (owner path), the parent becomes tickable, and a verdict ticks it → parent reaches N/N"). When the
last remaining vehicle legitimately carries `closes #tracker`, `check-pr-acceptance` reds on exactly that criterion
at every head — and no reviewer verdict, rebase, or amend can clear it, because the write-back is verdict-gated
(#1644) and the criterion's own truth is "the merges happened", which is false until the vehicle merges. The red is
the gate correctly refusing to let a PR self-certify a post-merge state.

- **Classify before dispatching anything:** if the sole unticked criterion's text names the merge/rollout completion
  rather than a file/behaviour the diff contains, the vehicle is **owner-merge critical path**, not an implementer
  defect. The sibling vehicles (each shipping its own slice) already merged; this one lands the last contract, and the
  reviewer ticks the PARENT's criterion (the one that becomes tickable) after this merge — never this tracker's own
  state criterion.
- **Do NOT loop-rebase, dispatch an implementer amend, or route a reviewer to tick it** — none can tick a criterion
  whose proof is the merge event. The honest moves: confirm the other ACs are `[x]`-proven (each with a `proven:`
  citation naming a reviewer lane + comment id + head sha), confirm the sibling PRs are merged, then hand the vehicle
  to the owner as the merge candidate with that one-line classification.
- **Confirm the guard red is the CURRENT state, not a pre-tick snapshot, before quoting it.** Compare the failing
  guard run's `completed_at` against the reviewers' tick comments' `created_at` at the same head:
  `gh api .../commits/<sha>/check-runs?per_page=100 --jq '.check_runs[]|select(.name=="guard")|"\(.completed_at) \(.conclusion)"'`
  vs the AC `(proven: … comment=<id> …)` citations' timestamps. A guard run that completed BEFORE the ACs were ticked
  is a stale snapshot (acceptance re-reads the issue live, so a rerun re-reads it — see the discriminator above);
  quote the freshness or it looks like a live red. A state criterion, however, stays unticked regardless of refresh,
  so its red survives any rerun — that is the tell that the criterion is post-merge, not stale.

## `closingIssuesReferences` is the ONLY authority on what a merge auto-closes — the body text is not

Before you accept or reject any merge-order decision that hinges on "merging X closes Y", read the
API field, never the visible body:

```bash
gh pr view <n> --json closingIssuesReferences --jq '[.closingIssuesReferences[].number]'
```

- **Never derive the close set by scanning the body for `#N` tokens.** A body legitimately names several
  issues in narrative — the audit that found the defect, the class of bug, an already-closed ancestor — while
  `closes` only ONE. Splitting the body on `#` yields a superset, and that superset makes a healthy PR look
  like it closes a tracker another lane is already implementing: a false one-vehicle conflict that gets you to
  re-dispatch or hold a correct PR. Grep only the literal adjacency (`closes|fixes|resolves #N`) for wording,
  and take the intended set from `closingIssuesReferences`.
- **A closing keyword only acts on ISSUES, never on another PR.** A body reading `closes #<PR>`
  (or a subject ending `(#<PR>)`) that names a PR auto-closes **nothing** on merge — the keyword is
  inert against a PR target. So "merging the child orphan-closes the parent PR" is a false alarm by
  mechanism; the child does not close the parent, and the parent must be merged or closed deliberately.
- **A `closes #N` inside a Markdown heading / prose label is UNRELIABLE IN BOTH DIRECTIONS — never infer
  the close set from the rendered text.** Measured both ways on the same heading form
  (`## Acceptance (closes #N)`): on one PR it yielded `closingIssuesReferences: []` and closed nothing,
  and on another the identical shape auto-closed the issue seconds after merge (timeline `referenced`→
  `closed`, actor = the merger). So do NOT reason "a heading never registers" (it does, sometimes) nor
  "the body says closes, so it closed" (it may not). Settle it on the API only: `gh pr view <n> --json
  closingIssuesReferences` for the intent, and the ISSUE's own timeline for the act —
  `gh api repos/<o>/<r>/issues/<n>/timeline --jq '[.[]|select(.event=="closed" or .event=="referenced")|
  {e:.event,at:.created_at,actor:(.actor.login//.user.login)}]'`. A close event within seconds of the
  merge, actor = the merger, is a merge-reference close (whichever body shape produced it); a close hours
  later by a bot workflow is the evidence/scan gate. Which one it was changes the remedy (see
  `finding-close-and-merge-state.md`).
- **Consequence for merge-order rulings:** when a lane/PM claims "A must land first or B's issue is
  stranded", verify the mechanism on the API for BOTH PRs. Empty `closingIssuesReferences` on both means
  neither merge auto-closes anything, so ordering is a rebase/green-path question (which base each needs),
  not a closure-safety one — and the issue in the middle stays OPEN until its owner closes it explicitly.
  Record the corrected mechanism on the issue the stale ruling touches, not only on the PR thread.

## Reproduce the gate locally before you dispatch an amend

The gate is a plain script with no CI-only state. Run the REAL one from the target head to decide
"gate defect / stale payload" vs "PR content defect" instead of inferring it from a red check name:

```bash
git -C <repo> show origin/main:scripts/check_pr_closing.py > /tmp/cpc.py   # never trust the primary clone's tree
git -C <repo> worktree add /tmp/wt-cpc <head-sha>                          # scratch worktree AT the head
cd /tmp/wt-cpc
python3 scripts/check_pr_closing.py check --body-file /tmp/body.md \
  --base origin/main --rev HEAD --head <branch> --title '<pr title>'
```

`check` prints `[check-pr-closing] OK …` when the head and body genuinely satisfy the gate, or
`N violation(s)` with the same evidence text CI prints. That OK line, quoted with the head sha, is the
proof that an amend is NOT owed and the red is the run's stale payload — put it on the issue instead of
dispatch a second amend. Remove the scratch worktree and its detach ref when done (this lane may remove
worktrees it created this turn; never another lane's).

### Run the WHOLE body-gate family in one audit — a pasted red transcript is one snapshot, not the PR state

An owner- or lane-pasted gate output ("N violation(s)" + `guard FAILED`) is evidence of ONE run against ONE
body state. Re-derive every body gate against the LIVE head and LIVE body before dispatching anything, and
post the result as a table with the head sha and exit codes:

| gate | invocation | what it grades |
| --- | --- | --- |
| acceptance | `check_pr_acceptance.py report --body-file <live body>` | linked issues re-read LIVE over the API |
| closing | `check_pr_closing.py check --body-file <f> --head <branch> --base <sha> --rev <sha> --cwd <repo>` | body/title + a real git range |
| hygiene | `check_pr_hygiene check --root <repo>` | the CURRENT CHECKOUT's commits and body |

Gotchas that each cost a wasted run:

- **`check_pr_hygiene check` accepts ONLY `--root`.** Passing `--head/--base/--body-file` (the shape its
  `report` subcommand takes) dies with `check_pr_hygiene: error: unrecognized arguments` — and because that
  argparse exit is not the last command in a pipeline, an `echo EXIT=$?` reads green. `check` grades whatever
  is checked out, so put a checkout AT the PR head first (`git fetch origin refs/pull/<n>/head:<ref>` then
  `git checkout -q <ref>` in the primary clone is enough and leaves no worktree); afterwards restore the clone
  to `main` and state that you did.
- **`check_pr_closing.py` imports root helpers by top-level name** (`base_ref`), so running the file directly
  from a copied `scripts/` dir fails ImportError. Run it as a package with both dirs on the path:
  `PYTHONPATH=<dir>:<dir>/scripts python3 -m scripts.check_pr_closing check …` (same for `check_pr_acceptance`).
- **A `check-pr-base` red on a branch whose base is merely OLD is EXPECTED, not a defect** — classify it before
  routing: `git merge-base --is-ancestor <base-sha> <main-tip>` true plus
  `git rev-list --left-right --count <base-sha>...<main-tip>` giving `0 N` means "N commits behind, re-basable",
  so a rebase is the whole remedy. A NON-ancestor base is a rewritten/diverged base and needs the rebase lane's
  diagnosis, not a plain nudge.

Consequence to state on the PR: when every body gate is OK at the live head and only `check-pr-base` is red,
that is ONE owed act (the rebase) — not a content defect, and not a reason to amend a body that already passes.

- **Do NOT pass the body into `make` through an env var.** `PR_BODY="$(cat body.md)" make check-pr-closing`
  dies with `unexpected EOF while looking for matching '"'`: the Makefile expands `--body-file "$(PR_BODY)"`
  and a multi-line body breaks the shell quoting, so the gate exits 2 on a CORRECT body — which reads as a
  red and sends you chasing a fix that is not owed. Write the body to a file and pass `--body-file <path>`
  to the python script directly.
- **Replicate the EXACT CI invocation, not `make` — the violation COUNT differs between them.** Bare
  `make check-pr-closing` (no `--body-file`) sources the body elsewhere and can report a different number
  of violations than the CI step, which runs
  `python3 scripts/check_pr_closing.py check --body-file <PR body> --head <branch> --base origin/main --rev HEAD`.
  Pull the LIVE body (`gh api repos/<o>/<r>/pulls/<n> --jq .body > /tmp/body.md`) and run that python form
  verbatim; only then does your count (and its per-issue breakdown) match what CI printed. A `make`-vs-CI
  count mismatch (e.g. 2 vs 5) is the `make` body source, not a moving target.

### A lane's amend/force-push STALES your fetched ref — the wire PR API is the head, a local ref is not

Remediation lanes habitually amend and `push --force-with-lease`, so a local `git fetch origin <branch>:refs/remotes/origin/<x>`
can be **rejected** (`! [rejected] … non-fast-forward`) while a PR-API read of the SAME moment shows a NEWER head. If you trust
the stale local ref you triage a superseded head: measured case — local ref sat at `804a42b7` (openspec gate red) while the PR
`headRefOid` was already `1c886e08` (openspec fixed); the "openspec still missing" finding was a phantom about a head that no
longer existed. Rules:

- **Read the head from the wire, not the tree:** `gh pr view <n> --json headRefOid,mergeable,headRefName --jq .headRefOid` is the
  authority. A failing `git fetch` line in your own output is the tell that your ref is stale — don't proceed past it.
- **Force-refetch before building the verify worktree:** `git fetch --force origin <branch>:refs/remotes/origin/<x>`, then
  `git worktree add --detach <wt> <that sha>`. Re-create the worktree at the fetched sha; a detached worktree left from the old head
  runs the OLD guard body and lies green.
- **Never quote a run id without pinning its `headSha`:** `gh run view <id> --json headSha` or `gh run list --json headSha` — a
  `failure` run at `804a42b7` is not evidence about `1c886e08`; classify each run against the head you actually mean.
- **The lane's "all gates green" is a claim; the wire run at the CURRENT head is the evidence.** Cross-check its claimed head sha
  against `headRefOid`, and read the failing STEP name (`gh api .../runs/<id>/jobs --jq '.jobs[].steps[]|select(.conclusion=="failure")|.name'`)
  — the surviving red may have MOVED (openspec closed → `check-pr-acceptance` now red), so "green" from the prior head proves nothing
  about the new one.

### The gate's justification grammar is literal — first-person notes are invisible, and a self-introduced gate must pass on its own PR

A PR that ADDS or edits `check_completeness()` (or any close-set gate) must pass its OWN gate at its head —
run the exact CI form above against the PR's own body before you accept a lane's "no findings on my own body".
Measured failure: the implementing PR redded `check-pr-closing` on itself while its author reported it clean.

- **The justification regex accepts only third-person.** `NOT_CLOSED` matches
  `(?:does\s+not\s+(?:close|closes)|(?:is|was)\s+not\s+closed)\s+#(\d+)\s+(?:because|as|since)`. A body that
  writes "We **do** not close #N because …" (first-person plural) does NOT match → the guard flags #N even
  though the note is on-record. When your remediation is "add a does-not-close note", it must read
  "does not close #N because …" (or "is/was not closed #N because …") verbatim; a natural first-person
  sentence leaves the red identical.
- **The check is pure-text: it flags a tracker-CLOSED issue named only in narrative.** `check_completeness`
  reads the body/commit text, never the tracker state — prose like "it fixed the #N truncation defect" (an
  ancestor described for context) is treated as a resolving reference to a live issue and reds demanding a
  close or a does-not-close note, even though `gh issue view <N>` shows `state=closed`. Do NOT fabricate
  `closes #N` to silence it (that asserts a closure that already happened); add the literal
  `does not close #N because <already-closed/different-issue reason>` note, and route the pure-text over-match
  (teaching the gate to skip closed issues / narrative references) to the ci-pipelines owner as a separate finding.
- **A `## Not covered` bullet reds `check_completeness` on the TRACKING issue it names when a resolving verb
  sits within the regex's 24-char window of the `#N`.** Two gates collide: the acceptance gate's
  `_declared_out_of_scope` requires the out-of-scope bullet to contain the criterion's leading 3 words
  verbatim, but when the criterion text itself carries a resolving verb ("one genuine **completed**
  success", "the measured band + the **completed** success") and the tracking issue number lands within
  ~24 chars of it, `RESOLVING` (`complet(e|es|ed|ing)` + `[a-z ]{0,24}?` + `#N`) reads it as a resolving
  reference to the TRACKING issue — which the bullet deliberately does NOT close — and `guard` reds
  "resolvingly names #N … no adjacent closing keyword". You cannot drop the criterion's words (the
  acceptance gate needs them) and must not add `closes #N` (a false close on a tracker). Remedy: reword
  the bullet so the verb and `#N` are >24 chars apart, or swap the verb for a non-resolving synonym
  ("completed success" → "green run") while keeping the criterion's leading 3 words. Confirm with the
  real `check_pr_closing` locally (resolving refs must be `[]`) before calling the body fixed — and note
  the body is event-frozen, so the red only clears on a NEW HEAD, not a rerun (see the stale-body section
  above).
- **Diagnose by the violation TEXT per issue, not the count:** "resolvingly names #N … no adjacent closing
  keyword and no on-record `does not close #N because` note" = a note/grammar problem above; "the joined
  commit messages close A; the body closes A,B — sets must be the same" = the body/squash-set mismatch
  (fix the side that lacks the literal keyword).

## Post-merge: prove the close-set actually LANDED on main (the PR is gone, the gate can't rerun)

After the vehicle merges, `gh pr checks` on a merged PR is not the question — but the merged PR OBJECT is still
fetchable, so a body gate CAN still be run against it (see the acceptance recipe below). For the CLOSE-SET,
verify the landed tree: two facts must AGREE —
the **merged/squash commit message** in `main`'s history carried the plain adjacent close, and the **PR
body**'s close-issue set equals it. That equality is exactly what the gate enforced pre-merge; proving it
post-merge is the "fix is real on main" evidence, not an assertion.

Use the re-runnable probe `scripts/verify-merged-close-set.py` (SKILL.md points to it): it runs the gate's
literal regex against BOTH the merged commit message and the live PR body, prints the two sets, asserts
equality, and — as a regression guard — checks that the FAILING form still fails (`closes **#N**` → no match)
and the fixed form matches (`closes #N` → match). A `MATCH: True` with the head sha quoted is the proof to
put on the issue; a `MATCH: False` means one side never got the close (route the amend per the fix section).

- **`gh api repos/<o>/<r>/pulls/<n> --jq .body` returns a RAW STRING, not JSON — do NOT `json.loads` it.**
  Piping it into `json.loads` raises `JSONDecodeError: Expecting value: line 1 column 1` and reads as a
  broken API call when the body was fine. Use the stdout directly (`.strip()`); reserve `json.loads` for
  calls without `--jq` (raw JSON object). Same trap as any `--jq`-trimmed field: `--jq` has already
  selected and stringified, so what you get back is the field's value, not a JSON document.
- **The regex must be applied from a FILE, not an inline shell pipe.** `echo 'closes #1704' | grep -E '\b…(?![#\w])'`
  silently reports `0` matches because the shell mangles `\b`/`(?!…)` before grep sees them — a false "gate
  still red". Put the literal regex and the text in a Python file (or the probe script) so quoting cannot lie.

### Post-merge: prove closure-honesty by running the ACCEPTANCE gate against the merged body

Merging does not retire the acceptance question — a PR can merge carrying `closes #N` while #N's `## Acceptance
criteria` still read `- [ ]`. The gate itself settles it, and it still runs because the merged PR object keeps its
body:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq .body > /tmp/merged-body.md    # works on merged PRs too
# copy the WHOLE scripts/ tree + root helpers from origin/main into a scratch dir (hidden imports), then:
python3 scripts/check_pr_acceptance.py check --body-file /tmp/merged-body.md
# OK — every closed issue's `## Acceptance criteria` is checked or named out of scope   ⇒ honest merge
```

- **NEVER hand-count acceptance checkboxes with a per-line or slice-truncated regex — run the gate.** A slice-cut of the body (`body[idx:idx+1500]`) or a per-line `- [ ]` scan gives FALSE counts two ways: criteria that WRAP across lines slip the line regex, and a truncated slice drops the criteria past the cut — either can make a legitimately-4/4-ticked merged issue read "1 open AC" and send you to file a `closes`-with-unmet-AC defect that does not exist. The authoritative count is `check_pr_acceptance.py report --body-file <live body>` (below), which parses the real `## Acceptance criteria` section; if you must eyeball it, read the WHOLE body and treat a wrapped continuation as part of its bullet. Measure-then-file: a `closes #N`-with-unticked-AC defect is only real when the GATE says so, never when a shell regex says so.
- **An `OK` proves either the boxes were ticked or each unticked criterion is named out-of-scope.** The exemption
  must name a **linked, OPEN** work item — confirm with
  `gh api repos/<o>/<r>/issues/<tracker> --jq '{state,title}'`; a bullet pointing at a closed/nonexistent issue is a
  hollow link and `OK` is not a licence.
- **Do NOT treat "linked-issue AC still `- [ ]` after merge" as an automatic violation.** Measure the `## Not
  covered` exemption first (the bullet must carry the criterion's leading 3 normalized words). Only when the merged
  body lacks it do you file the post-merge finding — naming the merge commit sha, the criterion and the run id — and
  route it to the owning lane. Never reopen the merged PR.
- **A DM claiming "freshly re-dispatched, all-green sweep" may cite a run that is already `cancelled` at some older
  sha.** Resolve the id (`actions/runs/<id> --jq '{status,conclusion,head_sha}'`) and compare `head_sha` to the merged
  head before repeating the claim; the remaining sweep thread is the linked tracker named in `## Not covered`, not a
  new dispatch.

## A close proves the issue was NAMED, not that its acceptance criteria were MET

Every gate above enforces the **close-set**: the PR body and squash text adjacently close the same issue(s). That
proves the PR *names* the issue it serves — it says nothing about whether the issue's own `## Acceptance criteria`
checkboxes were ticked. Two independent facts, and only the first is gated. Measured on this board: `check_pr_hygiene`
reads the PR body but never opens the linked issue; `acceptance_writeback.py` (#1644) ticks boxes **only on a reviewer's
COMMENTED verdict** and by its own docstring "an auto-merged PR with no reviewer verdict ticks nothing — an un-reviewed
merge stays honest (boxes unticked)"; `check_issue_body.py` validates the *producer scripts* render valid bodies, not a
live issue's criteria state. Consequence: a #491 auto-merge closes its issue reading 5/5 `- [ ]`, and the merge verifies
green — the repo's own definition of done (#745, "a criterion a reviewer cannot tick is not one") is never bound to
evidence at the one moment merge can measure it.

- **When verifying a merged PR as evidence, check BOTH halves.** The close-set (§above) and the issue's criteria
  (`gh issue view <n> --json state,body` — are the boxes ticked, and do the ticked ones match what the PR body claims?).
  A closed issue with unticked criteria is indistinguishable on the board from a proven-done one; report the discrepancy,
  do not read "CLOSED" as "satisfied".
- **The gap is an ABSENT VERIFICATION, not a bug in `acceptance_writeback`** — leave the #1644 verdict-gate alone (a
  merge with no verdict must still tick nothing; making it merge-driven would let an un-reviewed merge tick its own
  boxes). The fix is a separate merge-time gate that *reads* the issue + PR body and refuses silent-green, filed as its
  own refinement issue and routed to the preflight/CI owner (the same lane that owns body/preflight gates), never a
  patch to the write-back seam.
- **A gate on the issue side is red-on-old/green-on-fixed by construction:** a merged PR closing an issue whose claimed
  criteria are `- [ ]` must repro red before the fix and green after — demand that test pair on the issue. And the gate
  itself owes its own six-section acceptance criteria (its "done" is the boxes the PR can tick), or the new gate
  ships unverified by its own rule.

### `check-pr-acceptance` reporting `N violation(s)` on a live issue is the gate WORKING — do not dispatch a fix

Once `check-pr-acceptance` is functional (its own proc/parse defects cleared), a fresh run on a PR that closes an
issue whose `## Acceptance criteria` are still `- [ ]` prints `[check-pr-acceptance] K violation(s)` — one per
unticked criterion, each reading "acceptance item K … is still `- [ ]` … yet the PR body closes the issue." **This
is the gate holding the close exactly as designed, not a new defect.** It appears in `guard` AND `scope` (both run
the step) and derives into `ci-verdict` — three red check names, ONE expected self-red. Do NOT dispatch an amend or
a "fix" for it: the only thing that clears it is a reviewer COMMENTED verdict on the issue, which
`acceptance_writeback` (#1644) turns into ticks. The planner's move is to dispatch the **reviewer verdict**, never
the implementer. Verified shape: `gh run view <run> --log-failed | grep 'violation'` shows the K item lines; the
the step name is `make check-pr-acceptance` (Makefile target, e.g. :1104) and the job exits 2 with those violations.

- **A criterion the PR's own test suite PROVES, left unticked, is a TICK owed — not an exemption, not an implementer amend.** When
the only acceptance red is a criterion you can prove IS satisfied at the head, read the tests the PR carries and quote the
assertions that meet it, then route the reviewer to tick it with a `proven:` line naming the test + head sha. Measured shape: a
reviewer ticked the criterion its live run proved and left a sibling `- [ ]` whose negative control ("a genuine red still reds
— no gate weakening") the test file already asserted (`verdict == RED`, `counts["failure"] == 1`, the failing gate named for a
known red run). Do NOT file a `## Not covered` bullet for it — that marks a SATISFIED criterion as out of scope, the same
dishonesty as re-scoping a criterion to fit a diff, and leaves the record falsely claiming it was unprovable. Do NOT dispatch
the implementer — no diff changes an assertion the head already contains. The tick is the reviewer's act (the write-back is
verdict-gated); the planner's job is to hand over the proving test names and assertions, not to tick.
- **A lane's "CI verdict unquotable / transport degraded" is NOT a board state — read the completed guard run yourself.** When an
  implementer says it cannot quote the verdict, the question is not "wait for transport"; it is whether a run at that head reached
  a conclusion. `gh run list --repo <o>/<r> --branch <branch> --json databaseId,headSha,status,conclusion` (or
  `actions/runs?head_sha=<sha>`), then `gh run view <id> --log-failed`: a `completed/failure` run whose log prints
  `[check-pr-acceptance] K violation(s)` is a MEASURED red the lane simply could not read, and it wants the same reviewer
  dispatch as any other acceptance red. Post the correction naming the run id and the K item lines; never relay "awaiting
  transport" upward as if the gate were unresolved (an unread red and an unrun gate are opposite diagnoses).
- **Hand the reviewer the per-criterion proof you already verified, so its `proven:` line is immediate.** Before dispatching the
  write-back, read the head's committed artifact and record per criterion the file, its sha/line count, and the literal tokens
  that satisfy it: `git -C <repo> show <head>:<path> | wc -l`, `git show <head>:<path> | sha256sum`, and
  `git show <head>:<path> | grep -nE '<the refs the criterion names>'`. A reviewer told only "tick the boxes" burns a pass
  re-deriving what you measured; one given the head sha, the artifact's line count/sha and the satisfied tokens posts
  `proven: reviewer=<lane> comment=<id> head=<sha> rc=0` in a single step.
  **Do NOT conclude "content lost in the rebase" from an empty `git show` — an empty-success result is a PATH guess, not a
  missing file.** `git show <head>:references/<f>.md` prints nothing (exit 0) when the real path is rooted at the profile dir
  (`agents/<profile>/skills/<skill>/references/<f>.md`), which reads identically to a loss; a truly absent path errors instead.
  Resolve the path from `git show <head> --name-only | grep '<basename>'` before diagnosing loss.
- **Each `## Not covered` bullet exempts exactly ONE criterion — the acceptance gate matches it by the criterion's leading three
normalized words.** So a partial-tick PR reds on precisely the un-covered sibling: a bullet that exempts the `merge`-not-selected
criterion does NOT cover the `A genuine red` criterion beside it (the matcher needs that criterion's own leading words). "The body
already has a `## Not covered` section" is therefore NOT "every unticked criterion is excused" — read which criterion each bullet
names and match it against the K-violation lines before declaring the body complete.

- **Build the reviewer checklist FROM the gate's own log, not by hand-enumerating the issue.**
  `[check-pr-acceptance] N violation(s)` then one `acceptance item K ("<~40-char quote of the criterion>")` line per
  unticked criterion, each with the remedy ("tick via `acceptance_writeback` or name it out of scope under `## Not
  covered` with a linked work item"). Pull that block and post it as a numbered per-criterion checklist (K index +
  the quoted criterion + which issue it belongs to + the two remedies), so the reviewer acts on the gate's own
  enumeration instead of a transcription that can miss or invent a criterion. Get the log with `gh run view <run>
  --log-failed --job <JOBID>` or `curl -sL -H "Authorization: token $(gh auth token)"
  .../actions/jobs/<JOBID>/logs -o f` then `sed 's/\x1b\[[0-9;]*m//g' f | grep -iA2 'check-pr-acceptance'` — `gh api
  .../logs -o` writes 0 bytes (no `-o` on gh api, un-followed 302). A multi-issue PR groups the K items under
  different linked issues, so state each item's issue; the reviewer needs that attribution to route the tick.

- **A gate can be defeated in TWO independent ways — clearing one leaves it red on the other, so measure BOTH before
  declaring the gate "working."** Measured pair: (a) a **proc-routing defect** — a bare `subprocess.run(["gh",…])`
  inside the checker (no `# proc-allow:`, not through `scripts/proc.py`) reds the proc/lint gate so the acceptance
  step never meaningfully runs; and (b) a **parse-invisible body** — an issue whose `## Acceptance criteria` is
  hand-authored as a bold heading (`**Acceptance criteria:**`) with no `## ` section defeats `issue_body.section_body`
  (parses ZERO criteria → the gate is green-on-a-holds-closes) AND makes `acceptance_writeback.tick_acceptance`
  raise `BodyError` (the tick seam is unreachable). Fix both on their own vehicles — the proc defect to the CI owner,
  the body re-render to the planner (a planner-Ok body edit of the issue, not a code change) — then re-run and read
  the K-violation self-red, which is the first honest green-gate state. A run that reports "skipped" on
  `check-pr-acceptance` is telling you the gate did NOT evaluate; only a run that prints the K violations (or `OK`)
  proves it ran.

### When the verdict that would tick the criteria CANNOT exist yet — scope-note, never self-tick, never loop-rebase

`check-pr-acceptance` is normally cleared by dispatching the **reviewer verdict** (above). But a case exists where no
verdict is obtainable at the current head: the decisive proof run **cancelled** before the cell that proves the criteria
completed (see `actions-job-log-reading-midrun.md` §"a partially-cancelled run is not a verdict"), or the fix simply cannot
satisfy the criterion (e.g. an `--extra-index-url` reorder that cannot defeat a PyPI name-placeholder). Then there is no
honest tick path at this head, and the gate's own wording names the second remedy: **name the unprovable criteria out of
scope under a per-criterion note with the LINKED WORK ITEM that will prove them.** Concretely, post one board comment on
the PR that reads the linked issue's criteria one-by-one and states, for each: provable-now / not-provable-here + the
mechanism + the deepening issue that owns it. That converts the red from an unexplained hold into a scoped, tracked state
the next reviewer can act on.

- **Audit the LIVE body's `## Not covered` FIRST — a reported "PR closes #N with unchecked criteria" may already be
  remedied.** Before dispatching a reviewer write-back or an implementer amend for unchecked linked-issue boxes,
  fetch the PR's current body (`gh pr view <n> --json body`) and read its `## Not covered` section. Measured: a PR
  closing issues read as "unchecked criteria" while its body already carried a `## Not covered` bullet naming every
  one of them, tracked by an open deepening issue — which is exactly why `check-pr-acceptance` was GREEN. Then
  VERIFY the linked tracker is a real, OPEN issue (`gh api repos/<o>/<r>/issues/<n> --jq '{state,title}'`): a bullet
  pointing at a closed/nonexistent issue is a hollow link that fails the gate's completeness check. Also re-read the
  issue's LIVE checkbox state (`gh issue view <n> --json body`) — a pasted/older "items are `- [ ]`" snapshot is
  stale; boxes get ticked by reviewers between passes. Only when the body lacks the note (or the tracker is dead) is
  a write-back/amend owed.
- **Never self-tick (`- [x]`) an acceptance box to clear the gate.** The write-back is verdict-gated (#1644); a planner or
  implementer tick with no reviewer verdict is fabrication and the next reader cannot tell it from a proven one.
- **A DELIVERED claim that ACs were "written back" is verified by the `proven:` line, never by re-running the reviewer's proof.**
  When a bot DM/result reports boxes ticked, read each checked box's `(proven: …)` citation and demand it names a
  **reviewer lane + a comment id** and a **reproducible command with `rc=0 <sha>`** (or `run=<id>`) — e.g.
  `proven: reviewer=<lane> comment=<id> head=<sha> pytest <file> -q rc=0 <sha>`. That provenance is the discriminator
  between a valid verdict-gated write-back and a self-tick; a bare `- [x]` with no `proven:` (or one that names no
  reviewer) is a claim to reject, not repeat. Do NOT re-execute the reviewer's command yourself — the citation IS the
  contract, and an implementer citing `command+rc+sha` instead of a link to its own (possibly red) CI run is the
  honest-citation pattern, not a defect. A write-back is valid at an UNMERGED PR's head (the reviewer's evidence binds
  to that head); merge is a separate gate. Verify by `gh issue view <n> --json body` reading the box lines, and check
  the completion-record comment id resolves (`gh api repos/<o>/<r>/issues/comments/<id> --jq '{at:.created_at,login:.user.login,len:(.body|length)}'`).
- **Triage a batch of delivered bot results into actionable vs resend-acknowledgement — never reply to each.** A run of
  `bot_mode_dm --run-delivery` results can arrive together. A payload of `{"status":"claimed"|"queued", …, "detail":"Do not
  resend"}` or empty/truncated output is a **do-not-resend acknowledgement**, not a claim to reconcile — absorb it silently.
  The one item that carries a genuine state change (a named write-back, a landed head, a fresh run id) is the only one to
  verify against the wire; act on it and report a single consolidated result, not one response per delivery.
- **Never respond to an acceptance red with another rebase when `base == origin/main`.** `git rev-list --left-right --count
  <base-sha>...origin/main` printing `0 0` means the red is acceptance, not staleness — a rebase cannot change a checkbox.
  Measure base-vs-main BEFORE concluding "needs a rebase"; the same `BLOCKED` reads as an acceptance hold or a stale base
  and only that count tells them apart.
- The scope-note is a planner board act, not a branch edit: it does not touch the implementer's head, it just records which
  criteria are honest to leave for the linked deepening work item.

## A close-claim can be CATEGORICALLY unsatisfiable by its vehicle — check the criterion's named file against the diff, do not park on a live CI cell

A PR body carrying `closes #N` is not merely "criteria unmet" (above): sometimes the vehicle provably CANNOT meet #N no
matter what any running cell concludes, because the acceptance criterion names a file/path the branch never touches.
Measure this before you park routing on a verdict cell:

```bash
git -C <tree> show <head-sha> --name-only                                 # the vehicle's actual file set
git -C <tree> diff origin/main <head-sha> -- <the path the criterion names>   # EMPTY ⇒ categorically unmet
```

If that diff is empty while the issue's `## Acceptance criteria` read verbatim "`<path>` … <the change>", the close-claim
is unsatisfiable by construction: no test result, no rebase, no reviewer verdict can tick it. That SETTLES the routing
independent of CI — the close must leave the body (`## Not covered`, naming the tracked remedy) OR the missing change must
be folded onto the vehicle; there is no third branch where the claim holds. Post the impossibility (empty diff + the
`show --name-only` file set) and route it to the implementer; do not re-measure the in-progress cell as if it could
resolve a categorical gap.

- Distinguish from the "sets must be the same" reds above: those are body/commit-text mismatches an amend fixes. This is a
  DIFF-vs-criterion mismatch no text edit fixes — the vehicle's CONTENT, not its wording, is wrong for the claim.
- **The same test applies when the criterion demands LIVE evidence rather than a named file.** A test-only / docs-only /
  hardening diff (`gh api …/pulls/<n>/files` shows only `tests/**`, openspec, `docs/changes.d`, CHANGES) is a welcome
  gap-fill but categorically cannot produce a criterion that reads "`make build-engine …` completes SUCCESS in a real
  workflow run (head-sha bound)", an embryo job, or a bind-proof artifact. Read the criteria verbatim against the diff
  BEFORE routing; when they demand runtime evidence, give the lane two honest exits — (A) keep the PR as hardening, drop
  the `closes` claim from body and squash text, and prove the live criteria on an already-authorized verification run
  (cite its sha and the comment that authorized it) with `## Not covered` naming the tracked work item; or (B) re-scope
  the criteria through analyst/PM — never a lane's unilateral AC edit. Do NOT route such a vehicle to the reviewer: the
  reviewer can only honestly refuse, and the pass ends in the stuck-PR loop the gate exists to prevent.
- The verdict cell still decides the OTHER issues the PR legitimately closes; only the categorically-unmet one is
  independent of it. Split the two so one running cell does not hold the whole PR's disposition.

## Reproducing `check_pr_acceptance.py` locally: hidden imports and the LIVE body

`check_pr_acceptance.py` will not run from a bare `git show` of itself — importing it pulls `check_pr_authors.py` and
root helper modules (e.g. `base_ref`), so copy the WHOLE `scripts/` tree plus the root helper(s) from `origin/main`
(never the primary clone's possibly-stale tree) into a scratch dir, then run `report` against the body fetched LIVE:

```bash
mkdir -p /tmp/gate_run && cd /tmp/gate_run
git -C <repo> archive origin/main scripts | tar -x           # whole scripts/ package, not one file
git -C <repo> show origin/main:base_ref.py > base_ref.py     # root helper(s) the scripts import
gh pr view <n> --repo <o>/<r> --json body --jq .body > /tmp/live_body.md
python3 scripts/check_pr_acceptance.py report --body-file /tmp/live_body.md
```

`report` prints the linked issues and per-issue `K/N criteria ticked` — the same count the CI `guard`/`scope` step derives
into `ci-verdict`. Running it against the LIVE body (not the run's event-frozen `PR_BODY` payload) is what makes the
number authoritative NOW: a locally-run gate on a stale body reproduces a red that no longer exists, or misses a fix the
body already carries.

## check-docs: a behavioural change owes an `agent-wiki` note AND a `docs/changes.d` row (#1123)

Fixing a `check-pr-closing` red does NOT make a generated-bump PR green. The `scope` job's
`make check-docs` step then reds on an independent gate:

```
[check-docs] ERROR: change->note: this branch changes containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu (+4 more)
  but adds no agent-wiki/<stem>.md note — a behavioural change owes a note (and its docs/changes.d/<stem>.md row); see issue #1123
```

Rule: any PR touching an engine pin, dockerfile, or other behavioural surface must ship the
`agent-wiki/<stem>.md` note plus the matching `docs/changes.d/<stem>.md` row. An engine-bump
vehicle therefore owes BOTH the check-pr-closing body wording AND the docs note — dispatch them as one
amend on one vehicle, not two rounds. Never weaken `check-docs` (or `check-pr-base`) to clear a red:
both gates are correct and a suppression PR is a separate, reviewed decision.

**A plain script/code fix owes the change-note too — do not assume `check-docs` is engine-only.** A PR that touches
only `scripts/<x>.py` plus its tests still reds `make check-docs` (exit 2) for the missing `docs/changes.d/<date>-…`
row and `agent-wiki` note; the gate's notion of "behavioural change" is "the diff changes behaviour", not "the diff
touches a pin". So when diagnosing a fix-labelled PR's `scope` red, expect the change-note first and read the failing
step name rather than reasoning from the file paths.


## Second own-commit red class: missing trailing newline in change-note files

A lane's doc change-note files (`docs/changes.d/*`, the `agent-wiki` note) that
end without a trailing newline red `scripts/lint_linefeeds.py` — seen as `scope`
(and `ci-lint`) FAIL, 45s job, with the log naming "files missing a trailing
newline" plus the file list. It is a one-line file edit on the same branch, not a
content defect, and it usually rides alongside the adjacent-`closes` amend in the
same push. Read the log: `scope` red with a linefeed message is this; `scope` red
printing gate violations is the close-text defect above. Both on one PR = one
amend push, not two. **Sweep the lane, not just the one PR:** the same lane's
OTHER open change-notes frequently carry the identical linefeed red (it is a
habit in the note-writing step, not a per-PR slip) — when you diagnose one,
list the lane's other open PRs, read each `scope`/`lint` log, and hand ALL the
missing-newline files over in ONE dispatch so the lane does not re-trip the same
45s red across three PRs in three passes.

## "Patch-intact" after a rebase is a claim about FILE CONTENT, not close-texts — verify the close-set at every new head

A rebase lane reporting a batch as "all rebased, patch-intact, base-correct, head == origin" has proven the
DIFF survived and the base moved. It has NOT proven the squash-close texts survived. A rebase that re-authors
or normalises commit messages silently drops a `closes #N` that lived in the old message, and the PR then reds
`check-pr-closing` at its FRESH head — with the body still correct. So after any "patch-intact" rebase report,
before repeating the claim, run the classifier against EACH new head:

```bash
# regex: \b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)(?![#\w])  — one literal space, from a FILE not a shell pipe
for pr in <list>; do
  sh=$(gh api repos/<o>/<r>/pulls/$pr --jq .head.sha)
  body=$(gh api repos/<o>/<r>/pulls/$pr --jq .body)
  msg=$(gh api repos/<o>/<r>/commits/$sh --jq .commit.message)
  # sets must be EQUAL and non-empty; body set ≠ msg set (or msg ∅) ⇒ RED
done
```

Distinguish the three failure shapes this exposes, they have different remedies:

- **body has `closes #N`, head commit message ∅** — the rebase dropped the squash close; the body is correct.
  Re-author the head commit to carry the SAME adjacent `closes #N` (force-with-lease, `--force-if-includes`,
  no file diff). One amends the commit, never the body.
- **body has NO close at all, title cites the issue (`(#N)`)** — a claim with no closure anywhere. The fix adds
  `closes #N` to BOTH the body AND the head commit message (sets must match). Adding it to only one side reds
  the same gate.
  **EXCEPTION — a REFERENCE/pointer vehicle that must NOT close N is cured by RETITLING, never by adding a close.**
  The title's trailing `(#N)` is itself a `SUBJECT_CLAIM`, so a PR that merely points at a tracker ("this slice is
  part of the rollout, the tracker closes when all vehicles land") is red because its TITLE claims the tracker while
  its squash text closes nothing. Adding `closes #N` there is a false close on an umbrella — the exact defect the
  tracker section below forbids. Remedy: retitle so the title does not END in `(#N)` (move the tracker to prose — the
  claim regex anchors at end-of-line), which empties the claim set so "a change that claims nothing and closes
  nothing passes"; the squash subject usually needs no edit, making this a title-only change with no force-push.
  Optionally also give the body the literal `does not close #N because <reason>` note so the justification is on-wire
  under review churn (`NOT_CLOSED` needs the NUMBER after the verb — "does not close **it** because …" does not match).
  Decide by asking whether the PR is supposed to close N: yes → add the adjacent close to both sides; no → drop the claim.
- **the "fresh head" you are reading has a COMPLETED-failure CI run, not an in-progress one** — do NOT accept
  "frozen mid-compute" as the reason a PR is blocked. `gh api .../actions/runs?head_sha=<sha>` with
  `.status==completed && .conclusion==failure` is a landed red wave; only a genuinely `in_progress` run justifies
  "wait for it". Read the failing job/steps to classify before deciding it needs no action.

Ownership when the drop came from the rebase: the rebase lane that re-authored the heads is the honest owner of
restoring the close it dropped (it is the same lane, same push trail). The general "route to the author, not the
rebase lane" rule applies to an author-owned amend — a rebase-caused drop is the rebase lane's to repair. State
the exact per-PR remedy (which commit, which close set, #1088 held) and ask for each new head + fresh run id.

## The fix, and who owns it

- **Commit-message-only amend**: append the adjacent `closes #N` to the squash
  commit message, `git push --force-with-lease` (with `--force-if-includes`), no
  file-content change. Then re-read the `guard`/`check-pr-closing` run at the new
  head.
- **Route to the vehicle's authorshipping lane** (usually the implementer who
  opened the PR), NOT the rebase-conflict lane. A rebase lane will rebase the
  branch onto a current base and then correctly refuse to re-author another
  lane's commit message — it reports the residual and routes it back. Dispatching
  the amend to the rebase lane creates a two-writers / mis-scoped edit; dispatching
  to the author is one vehicle, one push.
- Keep it a single vehicle: amend the existing branch, never open a new PR for the
  same issue (#824).

## A NEW PR closing the PARENT PR is not the #824 duplicate — split by FILE DOMAIN

The one-vehicle rule forbids a second PR re-doing the *same issue's fix*. It does NOT
forbid a **chained fix-PR**: a new PR whose body says `closes <N>` where `<N>` is the
**PR**, not the issue, and which repairs a red that the parent PR's branch cannot itself
contain. Tell the two apart by the file sets, never by the fact that a second PR exists:

```bash
gh pr view <child> --json title,body,closingIssuesReferences,baseRefName \
  --jq '{t:.title,closes:[.closingIssuesReferences[].number],base:.baseRefName}'
gh api repos/<o>/<r>/pulls/<child>/files --jq '[.[].filename]'
gh api repos/<o>/<r>/pulls/<parent>/files --jq '[.[].filename]'   # compare domains
```

- **Different file domain ⇒ legitimate chained repair, keep both.** A gate/strict-pull
defect lives in `pipeline.yml`/`Makefile`; the issue's content fix lives in a
`Dockerfile`/script. The parent PR cannot carry the gate fix without mixing two
lane-owned domains, so the child PR (base `main`, `closes <parentPR>` and explicitly
"does not touch the <parent>'s fix") is the correct second vehicle. The chain reads
**child → closes parentPR → closes issue**; one PR per issue, no overlapping scope.
- **Same/overlapping file set ⇒ duplicate (#824), collapse to one.** Two PRs editing
the same files for one issue is the failure the rule targets: pick one on measured
merit, close the other with a comparison, say its diagnosis was not rejected.
- Do NOT block the child on the parent PR's red **— that red is exactly what the child
fixes.** Review it against current `origin/main` and its OWN head, not the parent's
failing checks.
- Record the reconciliation on the child PR so the next reader does not re-derive it
and mis-flag a valid chain as a duplicate (and vice-versa: do not wave a same-domain
second PR through as "chained").

## Identical TWIN PRs from a degraded create channel — one vehicle created twice, not a scope split

A lane whose output/terminal channel degrades can run `gh pr create` twice against the SAME branch,
producing two open PRs with the SAME head sha, byte-identical body, and identical check results —
seconds apart. This is neither the #824 same-fix re-do (which is two DIFFERENT branches) nor a chained
parent/child PR: it is literally one PR created twice.

Verify identity first — same `headRefOid` on both is the decisive fact, never the second number itself:

```bash
for n in <a> <b>; do
  gh pr view $n --repo <o>/<r> --json number,headRefOid,createdAt,isDraft --jq '{number,headRefOid,createdAt,isDraft}'
done
```

Same head sha + same branch ⇒ twins. Keep the EARLIER (`createdAt`), close the later with a short
comparison table (head, created-at, each check result) and a line that the diagnosis is **not
rejected** — this is dedup of one branch/head, not a ruling on anyone's diff. If the author already
closed one itself (a degraded channel often recovers and closes its own duplicate), there is nothing
for the planner to close — just confirm the survivor is the sole open PR on the branch:

```bash
gh pr list --repo <o>/<r> --head <branch> --state open --json number --jq '.[].number'   # expect exactly one
```

Never treat a twin's extra PR number as a second vehicle to reconcile, or as evidence that two lanes
collided — read the head sha; identical heads mean ONE vehicle, duplicated. The two PRs share every
check-run, so "both are red" is one red, and "both need the same fix" is one dispatch.

## Orchestrator checklist on a rebase-lane report that flags this residual

1. Read the failing `guard` job log at the reported head; quote the printed PR
   body claim and the gate name.
2. Confirm the defect is commit-message-only (no file diff needed) by the log text.
3. Dispatch the amend to the PR author/implementer with: the head sha, the gate
   name + run/job id, "commit-message-only, force-with-lease, no file edits, one
   vehicle", and ask for the new head + a completed green `guard` run.
4. Do not re-dispatch the rebase; it did its part.

## A PR closed UNMERGED orphans the follow-on scope its body named

A vehicle can be closed without merging (`state: CLOSED`, `mergedAt: null`, `closedAt` set) — by the owner token,
often after its checks went red. Its diff is discarded, so the lane that owned it truthfully reports the branch is
gone. But the PR body frequently names work BEYOND the issue it was nominally closing: new registry engines/entries a
live producer store introduces, decisions the weekly sync needs before it can land green. That named scope now has no
vehicle, and the issue it served may already be satisfied on `main` by OTHER merged PRs, so nothing re-raises it — the
next scheduled sync reds and no open issue owns the fix.

Verify BOTH halves before repeating a lane's "resolved / no PR" claim: (a) the issue's narrow scope on `main`
(`git grep -n '<entry>' origin/main -- <file>`, or `git show origin/main:<file> | grep`), and (b) the PR's real state
(`gh pr view <n> --json state,mergedAt,closedAt,headRefOid,body`). When main satisfies the narrow scope but the body's
named follow-on has zero entries on main, file a FRESH issue for the follow-on in the six-section shape — never reopen
the closed PR (its diff is gone; reopening resurrects a stale red branch) and never invent a test-churn PR to look
productive. Route it to the queue via the owning data-contract lane, naming the closed PR as the decision origin.

A closed-without-merge by the OWNER token is a correct owner act, NOT an unapproved-merge incident — only a
SELF-merge is the incident. Record the closed PR's number and close time in the fresh issue's Technical section, and
state explicitly that its diagnosis was not rejected, only its discarded vehicle.

### When reopening a closed-unmerged PR IS the right vehicle (the narrow-scope-still-unlanded case)

The "never reopen" above applies when `main` ALREADY satisfies the PR's narrow scope and only the body's
follow-on remains (reopening there resurrects a stale red with nothing left to merge). It does NOT apply
when the closed PR's own diff is still the correct, un-landed fix and its branch object still exists —
reopening is then the cheapest, honest vehicle (no new branch, no duplicate PR), and it is a board-state
act the planner may take without implementing.

Decide by measuring, not by the closed state:

```bash
gh pr view <n> --json state,mergedAt,headRefOid,headRefName,headRepositoryOwner,body
gh api repos/<o>/<r>/git/ref/heads/<branch> --jq .object.sha    # branch object still alive? (fork owner too)
git -C <repo> show origin/main:<the-file> | grep -c '<the-fix-marker>'   # 0 = fix genuinely absent = reopen
```

Reopen only when (a) `mergedAt` is null, (b) the branch ref still resolves at the head the diff needs, and
(c) the fix marker is absent from the live `origin/main` (grep count 0). Then `gh pr reopen <n>` and post
one comment naming it the open issue's vehicle. Crucially: **reopening restores the vehicle but does NOT
rebase it** — the head keeps its old branch point, so after reopen dispatch the rebase (see
`pr-head-location-and-base-gates.md` §3c: base-field ≠ rebase) and expect CI to re-run red on the stale
base until the real rebase lands. State that expectation in the reopen comment so the red does not read as
a new defect.
