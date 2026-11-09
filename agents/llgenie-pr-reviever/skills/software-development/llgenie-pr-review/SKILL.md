---
name: llgenie-pr-review
description: "Use when reviewing llgenie PRs: evidence, gates, verdicts."
version: 1.28.0
author: LLGenie PR Reviewer
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [github, llgenie, pull-requests, code-review, ci, gates]
    category: software-development
    related_skills: [github, containerized-repo-verification, worktree-branch-hygiene]
---

# Reviewing PRs on asimov-agent/llgenie

## Live profile is authoritative; never sync tree over live (owner, 2026-11-01)

The Hermes live SOUL/skills are the LATEST and authoritative — the tree's `agents/<lane>/` catches up to live via #791/#1062 versioning, never the reverse. Do NOT sync tree-content over the live profile (silently truncates accumulated live lessons). If live carries lessons the tree lacks, file+dispatch the versioning; do not self-edit to force green, do not trim live. A tree→live sync is legitimate ONLY for a versioned landing already merged on main.

## Bot-PR body gate (`AGENTS:`/`BASE:`)

See `references/body-gate-agents-base.md`; SOUL change: `references/authoring-versioned-soul-change.md`; polling: `references/ci-check-state-polling.md`. Write `$HOME`, never `/home/<user>`, in anything this profile authors: `references/write-home-not-absolute.md` (#2145). Acceptance write-back evidence (run at head OR `command rc=<n> <sha>`; never tick pending): `references/acceptance-writeback-evidence.md`.

<!-- host-bot-tools:begin -->

## Verdict tooling pitfall: self-approval is refused on the author's own PR

When the reviewer CLI is authenticated as the same account that authored the PR (here the whole fleet runs as `andyholst`), `gh pr review -a`/`-r` fails with GraphQL "Can not approve your own pull request". The `-a`/`-r` merge-state cannot be set from that token — it is not a retry-able failure. Still document the verdict AT the head via `gh pr comment` (quote sha, run id, each acceptance criterion, the -a refusal and why), name which thread must carry a reviewer-scoped token, and report the finding to the inbox. Never claim APPROVE state you could not set; say exactly why it was refused.

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `llgenie-pr-review`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## Role artifact (2026-11-01)

The artifact is the review comment: file, line, verdict, sha, and run id. Do not write the fix. `message_agent` to `llgenie-planner` with the PR number, the sha, the run id, and the verdict.

## Local verification depth

`references/local-verification.md` — the repo's own test venv and the `-s`/`-x` trap, golden/fixture
freshness (a golden can be in the PR diff *and* stale), measuring on the data path the test actually
uses, the control shape, **proving a new guard test discriminates by running it against a pre-fix
module with the head's test file bolted on (both-directions acceptance)**, the clean-HOME split for profile gates, and — for a baseline — the rule that
`git stash` is a no-op on committed work so the base needs a detached worktree. Read it before
publishing a local red **or** a local green as evidence.

## Dispatch protocol (fleet under the planner)

When the fleet is paused the reviewer does not choose its own work; `llgenie-planner` dispatches.
Every reply opens with a status line — a report without an id and a branch is not a report:

```
BOT llgenie-pr-reviever · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>
BOT llgenie-pr-reviever · no PR · idle · blocked on: none — no review requested yet · next: nothing until I dispatch
```

State limits in plain terms — never shorthand the reader must decode. When work is interrupted by the
per-turn tool-call cap, say it as *"I was cut off by the per-turn tool-call limit and resumed when a
new turn gave me calls again"*, not *"when the budget allows"* — in this setting "budget" reads as
money or resource, and the user has to ask what it means. Name the actual constraint (a turn's call
count) and the actual trigger (a fresh turn), never a metaphor.

**A delegated PR number can be wrong — resolve it by head sha / branch, never conclude the PR does
not exist.** A lane's delegation or hand-off can cite a number that 404s (`gh pr view <n>` →
`Could not resolve to a PullRequest`) while the PR is live under a different number: the head sha,
branch and title in the same message identify it. When the number fails to resolve, match it instead
of refusing — `gh pr list --state open --json number,title,headRefName,headRefOid` and pick the row
whose head/branch equals the delegated one, then review under the real number and say the correction
back to the delegating lane once. A wrong number is a typo in the hand-off, not a missing PR.

**A dispatch's "own gates green, only the review missing" is itself a claim — read the full rollup
before you start, or you will review a red diff.** A dispatcher can verify head/branch/`mergeable`
and still hand you a PR whose own-gate checks are red: measured on #1610, the dispatch said "all green
except review" while the head carried `linux/unit` FAILURE (`check-pr-base` — a stale base) and
`ci-verdict` FAILURE (its echo) plus the cross-PR `holds`; the planner retracted with "I verified
head/base/mergeable but not the full rollup". One read before accepting settles it:
`gh pr view <n> --json statusCheckRollup` (or `gh pr checks <n>`). If an **own-gate** check is red at
the head, that is not a reviewable PR — acceptance can't be measured against failed legs — so route it
back ("premise refuted: `<job>` red at `<sha>`, run `<id>`; own-gate red, not a review target") and
stand down, rather than posting an acceptance verdict on a red head. Do not delete a verdict you
already posted honestly (one that names the reds and says "rebase owed, not mergeable as-is") just
because the dispatch was retracted: that comment is correct board state, and it is the handoff the
owner lane inherits.

A dispatch must name the PR **and the head sha to judge** (branches move under you), and the rule
is that a verdict cites the run id at that head. Verdicts are **comment-only by default**; a
`do-not-merge` is allowed only with a one-line reason *and* a one-line unblock condition in the same
comment, and lifting it is the planner's call. If the run at the head has no conclusion yet, say
"no verdict exists yet — run `<id>` is queued" and stop; never manufacture a verdict and never move
a head to produce a fresh run.

### The verdict is an artifact SET, and the completion turn ends on a write

A verdict is not one object. Post all three, in this order, then verify each by id before you
report:

1. **The verdict state** — `gh pr review <n> -a` / `-r` (never a body-only comment). This is the
   row the board and the gates read.
2. **A durable record comment on the PR thread** — `gh api -X POST repos/asimov-agent/llgenie/issues/<n>/comments -F body=@file`
   carrying the same verdict text, the judged sha, the run id, and the one-line fix for each
   finding. A review body is the fragile artifact (a `-f`/path slip stores a literal filename and
   the state lands with no readable text); the record comment is what a later reader quotes.
3. **The source-issue record + acceptance write-back** — tick only the criteria this PR delivers
   (`acceptance_writeback … --proven <subset> --dry` then live), then post the record comment on
   the issue that owns those criteria. A dispatch threaded on the PR still needs the issue-side
   record: the AC row and the proof must live where the criteria live.

Verify on-wire per artifact: `gh api …/issues/comments/<id> --jq '{id,created_at,user:.user.login}'`
and a single-copy check (`select(.body|contains("<record title>"))` returns exactly the one id) —
batched retries have re-posted duplicate verdicts before, so a duplicate is deleted, keeping the id
your `(proven: … comment=<id> …)` marker pins.

**Finish the completion turn on the mutation, not on the read.** A turn whose last call is a
read-back is indistinguishable from a turn where nothing happened: end with the post/tick that
changed board state, and put the verification of *that* write in the same turn ahead of it. A
"task-relevant mutation" for this lane means a review, a tick, or a comment that a stranger can
find — a skill edit or a scratch file is bookkeeping, not the deliverable.


**One settlement, one acknowledgement — a re-acknowledgment reopens a closed loop.** Once a
correction or finding is conceded on-record by both lanes (the peer's message states `status: settled`
and both facts are measured), the thread is closed. A further *"confirming your confirmation"* message
is not politeness, it is a ping-pong turn: it forces the peer to either reply (loop) or hold silent
(reads as non-compliance), and it spends a shift on a settled question. Post the settlement **once** —
the facts, the sha, the on-record comment id — then stop. If a second delivery arrives that only
re-states your own already-acknowledged point, it needs no reply at all; noting it as delivery-only in
the status line is the whole action. The same applies to a settlement the peer already conceded: do not
re-post it to "close the loop harder".

**Never re-send a DM or re-issue a post because a batched tool read looked like a
"transient failure".** `bot_mode_dm` queues durably and redelivers; a delivery that returns
`status: queued|claimed` (or a batch whose read results arrive late) is *pending*, not lost. A retry
of the same message lands as a duplicate the peer must answer again — measured this session: a batch
of mis-fires was redelivered three-plus times and each copy drew its own planner settlement. Read the
delivery status (`queued`/`claimed` = retained, do not resend), send each DM once, and treat a
replayed redelivery of your own already-settled point as delivery-only in the status line, never a
reason to send again.

**An auto-merge APPROVED is seconds away from a merge — re-read `state`/`mergedAt` BEFORE posting your verdict, or you post a ghost-frame on a merged PR.** The #491/#1088 approve-then-merge class stamps APPROVED and merges ~5 s later (measured #1655: APPROVED 06:55:01Z → MERGED 06:55:07Z; #1681: APPROVED 07:19:18Z → MERGED 07:19:23Z; #1674 likewise). If you discover the auto-merge APPROVED and your verdict would post after `mergedAt`, no verdict is owed at all: a closed/merged PR is not a head to grade ("freeze or say nothing"), the content you judged is already on main, and posting late reads as a ghost-loop the planner must correct. What survives on a merged PR is only the evidence fold: report the APPROVED id + `submitted_at` + merge delta to the planner for the #1088 set, never a re-grade. One read settles it before you post: `gh pr view <n> --json state,mergedAt,mergedBy`.

**A correction that arrives mid-flight can be crossing a MERGE — read `state` before acting on it.**
A planner DM saying "STOP, your verdict reviews a superseded head / a rebase is owed" may have been
composed before the owner merged the PR; acting on it then re-opens a closed loop. Before conceding or
re-dispatching, one read: `gh pr view <n> --json state,closed,mergedAt,mergedBy,mergeCommit`
(`state=MERGED`, non-null `mergedAt`). If the PR is already merged, the correction is moot — report
"merged <time> by <login> (merge commit <sha>), the correction is against pre-merge state" and stop; do
not "retire" a verdict line on an already-merged PR, and do not re-post the verdict. The same read
also settles the `merged`-vs-`closed` field trap above: there is no `merged` boolean, `state=MERGED` +
`mergedAt` is the fact. When the newest comment on the PR is `<!-- auto-merge: merged <sha> -->`,
the arms-lane already operated — re-read `state` before assuming a comment you posted is still the tip
of an open review.

## A versioning PR is a checkpoint, not a state

"All N files match live" is a measurement at a named head, and it expires the moment the merge lands.
Measured twice in one night on this lane:

```
23:54Z  branch b08c1ef4 vs live  → 0 of 10 differ      (true, and reported as a state)
00:09Z  #1136 merges → main 864fffaa
00:37Z  main 864fffaa  vs live  → 4 of 10 differ, ~8,197 b live-only
        SKILL.md +1,860 · base-and-merge-integrity +1,267 · evidence-and-bases +1,196 · gate-auditing +3,874
```

Nothing was merged wrong — the merge froze the tree at the branch's content, and the lane kept writing
to the profile afterwards. **That is the second-order form of the drift a versioning PR fixes:** the
first is "live grew and the tree was never updated"; this one is "the merge is a snapshot, and
everything after it drifts again".

So the comparison is a **post-merge** step, not a pre-merge one, and it is run against `origin/main` —
the only baseline that survives a merge:

```bash
git -C <repo> fetch origin main
for f in $(git -C <repo> ls-tree -r --name-only origin/main agents/<lane>/); do
  git show "origin/main:$f" | sha256sum; sha256sum ~/.hermes/profiles/<lane>/${f#agents/<lane>/}
done
```

Report it as *"N of M differ at `<sha>`, measured `<hh:mm>Z`"* — never as "the tree matches live",
because that sentence has no expiry and will be false within the hour.

**A vendored tool's honesty is byte-identity *and* execution, re-proved at the merged tip.** A digest
comparison proves the merged copy equals the live one; it does not prove the copy runs. When a
vendoring PR merges a lane tool (script + its test), add one execution step at the merged sha in a
detached worktree: run the entrypoint so it reads the live board clean (`--help` or a full tick, rc=0)
and run its test module (`pytest --noconftest -q <test>` → quote `N passed`). A byte-identical copy that
aborts on import is an honest-looking artifact that lies; the pair (equal digests **plus** a green run)
is the acceptance, and the worktree is removed after. This closes the continuous-improvement loop when
the reactive queue is empty: re-audit at the merged sha, record "re-audited at `<sha>`, no findings" with
the digest pair and the test count.

**The other direction — a reload directive — syncs the LIVE profile FROM main; see
`references/live-profile-reload.md`.** The versioning-PR comparison above fixes *live grew, tree behind*;
a "reload SOUL and skills from main" directive is the opposite — `main` landed a change and the live copy
is stale, so the remedy is `git show live/main:agents/<lane>/<rel> > ~/.hermes/profiles/<lane>/<rel>` per
diverged file, re-diffed to `MATCH`. No PR: the behaviour is already merged, you are only aligning a
derived copy.

## The skill body has a size ceiling, and it fails silently

`skill_manage` refuses a save once `SKILL.md` passes roughly **100,000 characters**, and the refusal
reads `batch aborted, all touched skills rolled back`. A refused save looks like a save: the lesson
lands nowhere, or lands only in the duplicate profile copy — which is how a lane can appear to "keep
forgetting" lessons it keeps writing down. It is a mechanism, not a discipline problem.

Measured on this skill: **100,688 b** and every save refused; after moving the 628-line
`## Standing rules for this repo` section verbatim into
`references/standing-rules-for-this-repo.md` (pointer left at its heading), **41,498 b** and the save
succeeds. **A lesson recorded in the same edit that clears the cap is the only evidence the cap moved.**

So: when a lesson will not save, measure the file's **character** count first — the ceiling is a
character cap, and `wc -c` reports **bytes**, which overstates a UTF-8 file (`SKILL.md` measured at
100,417 bytes is only 99,828 chars, i.e. under the cap). Read the character count, not the byte
count, before concluding a file is over the line:

```bash
python3 -c "print(len(open('SKILL.md').read()))"     # characters — the number the cap counts
wc -c SKILL.md                                        # bytes — NOT the cap (multibyte inflates it)
```

A delegation that says a file is "over the 100,000-char cap" when `wc -c` reads 100,417 is the
bytes-vs-chars artifact, not a violation — verify with the `len()` read before trusting the alarm.
If the character count really is near the ceiling, move the largest self-contained section
**verbatim** into `references/`, leave a one-line pointer, then verify with a line-by-line
`missing: 0` check — never eyeball a split, and never split by concatenation.

**Verify a split by grepping for the rules that must STAY, not by reading the pointer you wrote.**
A split moves whatever you selected, and the section boundaries do not know which sentences were
load-bearing. The check is mechanical and it fails in the direction you least expect:

```bash
for p in 'never merges' 'gh pr review -a' 'gh pr review -r' 'working on #' 'REVIEW_REQUIRED';
  do printf '%-40s ' "$p"; grep -ci "$p" SKILL.md; done     # every count must be >= 1
```

Measured: after moving a 628-line rules section out, the lane that wrote the acceptance criterion
("never-approve/never-merge stays in the body") still had `grep -ci 'never approve' → 0` — the rule
survived only in the reference, behind the hop the acceptance existed to forbid.
`never-merges, no squash, no auto-merge` are the constants that must stay in the body (issue #1193
changed the approve side to the load-bearing `-a` / `-r` verdict, never the merge side). **An
acceptance you authored is not evidence you met it**; grep the body for the sentence, and if it moved,
put it back
above the pointer. The pointer should name what is behind it, never carry the only copy of the rule a
review cannot start without.

## Standing rules for this repo (they override generic review habits)

**One rule never needs a second lookup: this lane never merges.** No squash, no auto-merge, no
`gh pr merge` — a merge is the owner's, never this lane's. `agents/manifest.json` declares
`never-merge` for this profile.

**The review verdict is load-bearing state (issue #1193):** `gh pr review -r` when the head fails an
acceptance criterion — naming the criterion, the head sha and the run id — and `gh pr review -a` when
every criterion is met, with the same evidence anchor. `gh pr review -a` means the code met the issue's
acceptance criteria at the measured head and sha; it is a verdict the owner and the gates read, never a
merge authorization. This lane never merges what it approves, and never approve-merges bypassing rule 16.
A neutral body-only comment with no `-a` / `-r` is not a conclusion; re-post it as a review with the
verdict state the board can see. A green PR is handed off in one line to the lane that owns it.

The rest of the standing rules live in
**`references/standing-rules-for-this-repo.md`** — the author gate, hold discipline,
push and rebase behaviour, and the CI-read rules. Load it before acting on any of those; the always-on
summary a review needs without a second lookup is below in `## What actually blocks a PR`,
`## Verdicts` and the evidence block.

## Fleet rules 13–16, verbatim (from #873's body at commit time — do not paraphrase when citing)

**Reviewer annotation on rule 13 (not part of the verbatim quote).** A hold is NOT lapsed merely because its target issue CLOSED — read the closing commit's DIFF against the issue's tracked acceptance criterion before lifting. A commit's title or message can name the issue without touching the remedy (a cache-warm change titled for a timeout issue is a mitigation, not the timeout-cap raise). If the actual remedy lives in a separate OPEN issue, the tag stays and that issue's landing is the lift condition — name its number. "Closed" is a state of the issue; "remedy landed" is a fact about a diff, and only the second lifts a hold.

**13. Never hold a PR without a remedy.** `do-not-merge` means "there is a concrete defect with a tracked
fix", never "this lane would rather not". Never place it unless the PR is **totally wrong or conflicting
with something** — and if you do, **file the issue that will make the tag removable**, name its number in the
PR comment with the exact condition for removal, and **remove the tag yourself** when that issue lands
(naming the sha or run id that proves it). A PR a bot implemented can never carry `do-not-merge` by default;
"I am not confident" is a review, not a label. A hold whose reason expired is indistinguishable from
abandonment on the board — `mergeStateStatus` reads `BLOCKED` either way. **If you cannot name the issue that
fixes it, you are reviewing, not holding.**

**14. Announce the work where the work lives, and talk to the lane you overlap.** Before you pick anything
up, **comment on the issue or PR** saying what you are taking, on which branch, and what "done" means — a
claim is a comment a stranger can find, never a DM and never private memory. **Re-read that thread before your
first edit**: an existing claim, a live branch, or a note from the lane that touched the files last outranks
your plan. When two lanes are on the same files, or one lane's change moves the other's premise, **message
that lane directly** with the id, the sha and what you need — then **post the conclusion in the issue**,
because a decision that exists only in a DM does not exist for the next reader. Rebase, rewrite, or force-push
on a branch another lane is working is a conversation first, a command second. Silence between two lanes on
one set of files is how a green gets discarded twice.

**15. Start from a fresh upstream main, and bookend the work with two comments.** Before you create a
worktree, branch or first edit: `git fetch upstream main` (the canonical remote is `asimov-agent/llgenie`; a
fork named `origin` is not upstream) and branch from `origin/main` **at the sha you fetched in that moment** —
never from a branch you already had, and never from a sha quoted in a chat message, which is stale by the time
you read it. Write the sha you branched from into your first comment. Then **bookend**: one comment when you
start (issue/PR id, branch, the main sha, what "done" means) and one when you finish (head sha, what changed,
the run id or command that proves it, and anything left open). **Report the same two lines to the planner**,
who relays the fleet's state back to you, so a lane never acts on a premise someone else has already
invalidated. A start comment with no finish comment is an abandoned claim; a finish comment with no start
comment has no baseline to compare against.

**16. Arm auto-merge when the work is done, not when it is approved.** The last push is the trigger:
`gh pr merge <n> --squash --auto`, then **read `autoMergeRequest` back** and report the arm time in
the same comment — `gh pr merge --auto` exits 0 and arms NOTHING when the base is not the default
branch (issue #964), so the exit code is not the fact. "Done" triggers the arm, not "approved". The
one exception is a PR the owner has explicitly forbidden: report `auto=none (owner instruction)` and
say where that instruction lives.

**In this lane rule 16 means the report, not the push.** This lane owns no PRs and merges none: a
verdict reports `auto=armed|none` (with the reason when none — draft, hold, `DIRTY`, non-`main` base)
and hands a mergeable-but-unarmed PR to the lane that owns it in one line — "green at `<sha>`, run
`<id>`, `CLEAN`, unarmed — arming is yours." Running `--auto` on a branch this lane did not author
would bypass the lane that owns it, and `agents/manifest.json` declares `never-merge` for it. The
retired **"arm at PR creation"** bullet is not part of this lane: it exists for lanes that open pull
requests, and a file carrying both it and rule 16 contradicts itself (measured on #919 at `4fb3bf3a`:
`:20` "no auto-merge, no `gh pr merge`" beside `:73` "arm at PR creation").

**When a dispatch asks for an act this lane's own SOUL forbids, decline once — and route, never
re-litigate.** A versioned lane charter outranks a dispatcher's instruction, so the answer does not
change when the request is repeated: state the ground (the charter sentence that names the act), name
who *can* do it (the owner, or a lane holding that grant), and stop. Repeating the reasoning on each
request spends the shift on a settled question; silence looks like non-compliance and compliance
breaks the chain that makes the verdict worth anything. **A reviewer that queues or approves its own
PR has removed the check the board exists for**, and holding the credential to do it is not consent to
use it — say that gap out loud, because a rule that survives only because a lane remembers it is one
hand-off from being broken.

**Companion owner rules (#948), same block:** `do-not-merge` only for genuinely wrong or conflicting work,
never as a default or a placeholder, and the tag comment must name the issue that resolves it or the tag
cannot come off. **A merged PR must never carry the tag** — remove it and say why in one line. Comment on the
issue *and* the PR where the work lives when you start and when you finish.

### Reviewing a `do-not-merge` PR against its lifting issue (#949 template)

When the ask is "check the five criteria in the lifting issue and say which line makes the tag
removable", the verdict is per-criterion, measured, and the tag is **not** touched:

- Run the two named modules at the PR head **and** on `origin/main @ <today's sha>` in the same
  breath; `5 failed, 20 passed` at the head with `25 passed` at the baseline means every red is the
  branch's, and the baseline sha makes that a measurement not a claim.
- A gate's failing **case** is the evidence, never its passing count: `test_every_dispatchable_workflow_has_the_guard`
  failing on `scope.yml` means "a dispatchable workflow carries no guard", which is the privilege
  hole (issue #295). Quoting "2 of 5 criteria fail" is weaker than naming the workflow.
- Distinguish *why* a job fails: `ci-scope` red on `[changes-index] … is not indexed` is the shared
  missing-note base (#855/#915/#940 family), not necessarily #904's classifier. Say which of the two
  it is — a doomed-to-fail-before-rebase criterion and the PR's own guard gap are different fixes.
- **Do not remove the tag** on an owner-applied `do-not-merge`; the review is what the owner lifts
  on. Name the exact acceptance line that flips it ("the tag stays until this lands", criterion 1 →
  `0 failed` at the rebased head with `scope.yml` in `_guard_steps()`).

## Loop

```bash
R=asimov-agent/llgenie
gh pr list --repo $R --state open --limit 100 --json number,title,author,headRefOid,headRefName,baseRefName,isDraft,reviewDecision,mergeStateStatus,mergeable,labels,statusCheckRollup
gh pr checks <n> --repo $R                 # triage from CHECKS, not `gh run list`
gh pr view <n> --repo $R --json files,body,commits,comments,reviews
gh pr diff <n> --repo $R > /tmp/pr<n>.diff
```

Re-read `headRefOid` on every pass: a branch can be rebased under you (the rebase bot and
the peer maintainers do it), and a verified head sha is the only thing your verdict applies
to. Verify **at the PR head in a worktree**, never from the description:

```bash
git -C "$HOME/repository/git/llgenie" fetch origin pull/<n>/head
git -C "$HOME/repository/git/llgenie-wt/<name>" status -sb   # reuse an existing tree if present
# else: git -C "$HOME/repository/git/llgenie" worktree add --detach ../llgenie-wt/pr<n> <sha>
```

`origin` in this clone is the UPSTREAM (`asimov-agent/llgenie`); the fork is `fork`
(`andyholst/llgenie`) — the opposite of the usual layout.

## What actually blocks a PR

| Signal | Meaning |
|---|---|
| `mergeStateStatus: BLOCKED` | a gate is outstanding — usually the required review or a pending check. NOT a conflict. |
| `mergeStateStatus: UNSTABLE` | checks still reporting; `auto_merge.py` needs `CLEAN`, so an unstable PR cannot land yet. |
| `mergeStateStatus: CONFLICTING` / `mergeable: DIRTY` | the merge would fail; needs a rebase. |
| `macos / unit` **pending** | a scarce macOS runner still holding the run; the PR sits `BLOCKED` while everything else is green. Say that, never "failing". |
| check conclusion `SKIPPED` / `ACTION_REQUIRED` | a form-driven placeholder (`test-published-${{ matrix… }}` is normal) or a human gate — not a test failure. |
| check conclusion `CANCELLED` | **not a failure and not a verdict**: a cancelled/superseded run cancels every sibling job, so a green PR shows a page of `cancel` rows. Report it as "needs a fresh run" (`gh run rerun <id>` at the same head), never as red — and never push an empty commit to fake a fresh run. `pr_watch.py` therefore counts `cancel=` separately from `fail=`. |
| `holds` check **fail** on a PR that is otherwise all-green | the repo's cross-PR hold gate — it is commonly ANOTHER PR's `do-not-merge` that this branch rides on, not this PR's defect. Confirm the held PR is proof-green at its own head (`gh pr view <held> --json state,headRefOid`) and exclude the `holds` row from the verdict, naming it as excluded. Folding it into "not green" accuses an innocent branch. |

## Repo gates that a change must satisfy (pick per diff)

`ci-unit` chain in `Makefile`: `skills-validate` → `check-engine-skill-gap` →
`check-engine-params` → `check-engine-coverage` → `check-engine-source` → `check-wiring` →
`check-secret-output` → `check-docs` → … plus `openspec` (Linux **and** macOS) and
`check-pr-authors`/`check-pr-hygiene`. A new user-facing make target needs, in order:
`.PHONY`, a `DEFERRED` entry in `scripts/issue_bot_gates.py` (never `FAST_GATES` — its
membership is a contract asserted by a test; the enforcing test is
`tests/test_issue_bot_gates.py::test_the_real_tree_is_wired`, and an unclassified ci-unit
target reds it with an `AssertionError` that names the target and prescribes "add it to
FAST_GATES … or to DEFERRED with the reason it is not re-checked") — the loudest miss because
`.PHONY`/`check-docs`/`check-wiring` can all pass while this one line is absent — a mention in `README.md` or a linked
`docs/` page (`check-docs`), and a truthful "CI" help line (`check-wiring`). Every
`openspec/changes/<name>/tasks.md` box must be ticked in the code commit.
See `containerized-repo-verification/references/llgenie-engine-pipeline.md` for the
engine → image chain and `worktree-branch-hygiene/references/llgenie-repo-notes.md` for
the gate order and flakes that are not the author's. A diff under `agents/<lane>/` — including a
vendored lane tool in `agents/<lane>/scripts/` — is judged by the byte-identity gate, not by reading
the file list: `references/agent-profile-tree-review.md` carries the gate commands, the one-directional
blind spot (a live-only file is invisible to it), and the four-step byte-copy procedure for vendoring
a live-only tool (copy script *and* test, prove identity by digest + empty diff, name the path in
SKILL, and read each gate's own scope before reshaping the copy). For keeping a verdict tied to a real base —
rebasing off a squash-merged ancestor, re-verifying your findings on the merged sha, the stale-base→
`check-pr-base` short-circuit that CANCELS the walking legs (no unit verdict at that head), the
`git fetch … --force` trap that leaves you measuring a stale `live/main`, and a cited WITNESS head
that went stale because the PR's branch advanced (a fresh-all-green AC witness must be re-anchored
to the branch's live head at measure time) — see
`references/base-and-merge-integrity.md`. For a POST-MERGE / chain-gate main-green run whose only
red is `check-pr-base` with `foreign commits (0)` (= phantom base-staleness from a sibling fleet
merge advancing main mid-run), re-anchor to the fleet-complete tip and never fabricate a green —
`references/phantom-check-pr-base-fleet-merge.md`. When an engine-build/workflow run sits `pending`
for hours, do NOT call it a producer stall from status alone: read `updated_at` — pinned-amended
`updated_at ≈ created_at` = concurrency-gated (never started), and a re-dispatch only queues behind
`references/concurrency-gated-pending-vs-stall.md`. Before you accept ANY dispatch red-attribution
("these N reds are the tracked <issue> cascade, do not weight them"), read the failing legs' own
logs and match the GATE to the log — a cascade tag can launder a real unrelated gate red (measured:
a scope red that the dispatch called #1862-class noise was actually a genuine `check-docs` #1123
error the PR's diff caused); reproduce locally when the log is ambiguous, and post the finding with
the exact gate message + owning lane (`references/dispatch-red-attribution-vs-leg-log.md`). When a
gate-corrective record says "rebase owed" and the PR later merges, the old claim is a false
instruction until retracted — retract on the same thread quoting both shas and close the row
explicitly (same reference, "superseded by a merge"). A described-but-never-posted corrective is a
pre-merge reversal: verify what is actually on the wire, withdraw before posting, and acknowledge
the reconciliation on the same thread (same reference, "described-but-never-posted").

### Reviewing a PR of a specific shape (workflow-add, reviewer-pass, hardening, data-sync, skill-admission)

Per-shape recipes live in `references/review-recipes-by-pr-type.md` — load the matching subsection for a PR
that adds a workflow file (odd-cron / dispatch-forms / guard byte-identity / import-root ratchet, and the
gate-relaxation checks), reviews named diffs, closes a scanner finding, vendors a data file, or admits a host
skill. The through-line they share: the PR's own test file is not the acceptance — the repo-wide convention
gates on `linux/unit` are, and the verdict names each failing gate + its one-line fix rather than calling the
whole PR wrong.

## Traps that cost real time

- **`docs/ARCHITECTURE.md` is generated and its census goes stale fast, and it goes stale
  *again* the moment anything merges.** The `architecture-bot` (cron `47 */6 * * *`, issue
  #449) rewrites it as one issue + one PR, and the numbers describe the commit the bot
  measured. A bot PR rebased onto newer `main` keeps the OLD numbers and lands already
  wrong — and a refresh measured against a base that merges before its own merge is wrong
  too. Always census the branch's **current** merge base (`git rev-parse origin/main`), not
  the base you measured an hour ago. Verify with the bot's own census
  (`scripts/architecture_bot.py:tracked_files` is just `git ls-files`):
  ```bash
  git ls-tree -r --name-only <head^> | wc -l
  git ls-tree -r --name-only <head^> -- scripts | wc -l
  git ls-tree -r --name-only <head^> -- tests | grep -c 'test_.*\.py$'
  ```
  A mismatch on `HEAD^` is a blocker (stale census ⇒ `do-not-merge`), and `git ls-tree`
  counts differ from `ls -d dir/*/` — use the `git` form, that is what the generator counts.
  Reviewing a census PR means recomputing **every** number it touches, not the headline one: the
  qualifiers in the same sentence (`skills/engines/` subdirectory count plus its `README.md`,
  `openspec/changes/` directory count, the `N tests/test_*.py` figures — which appear in two places)
  are claims too, and each is one `git ls-tree` away. Finish with `make check-docs` (exit 0, and quote
  its `[check-docs] ok: …` line) because that is the gate the change must pass. Run it directly as
  `python3 scripts/check_docs.py check` — it takes only `--root`/`--base`, **not** `--rev` (`unrecognized
  arguments: --rev` is a CLI-shape error, not a docs failure), and with no `--base` it lints the whole
  tree at the checked-out head; its `ok:` line counts every user-facing make target, every
  `agent-wiki/` entry's index row, and the `CHANGES.md` link set. Say plainly which
  number you could **not** re-derive from the tree (e.g. an engine-count line that reads the registry)
  instead of letting silence imply verification.
  Fixing a census is legitimate review remediation: edit only the numbers, keep every
  non-census sentence, commit as `Asimov Agent <support@docondee.com>` (or `Andy Holst
  <andy.holst@protonmail.com>`) so `check-pr-authors` passes, push on top (no force-push),
  and re-run `make lint check-docs`.
- **`tests/conftest.py` needs the gguf venv, so run a single test module with `--noconftest`.** It
  imports `scripts.llgenie_serve` (gguf+numpy) and a plain venv dies with exit 2 and no output — the
  silent exit 2 is a missing import in the venv, not a failing test. Two things make a scratch venv
  work in a repo worktree: `--noconftest` and `python -m pip install -q pygments` (pytest imports it,
  and without it the failure looks identical to the conftest problem). Then:
  `python -m pytest --noconftest -q -p no:cacheprovider tests/test_<name>.py`; for the whole suite use
  the container path (`make test-unit`, ~12–13 min). Do not conclude "the tests do not run here" from
  one empty log — retry with the module installed and quote the real `N failed, M passed` line.
  **A module that imports a sibling under `scripts/` (e.g. `from scripts import check_pr_closing` which
  then imports `base_ref`) needs `scripts/` AND the repo root on `PYTHONPATH`, or it dies at collection
  with the same exit-2 / bare `ImportError` and reads like the empty-log conftest artifact — a clean
  env is not a broken test.** Prefix the exact same command with it and the collection error becomes a
  real green: `PYTHONPATH="$PWD/scripts:$PWD" python -m pytest --noconftest -q -p no:cacheprovider
  tests/test_<name>.py`. Measure the module at the PR head in a worktree and quote the full count
  (`27 passed`) — that count is the acceptance evidence the earlier bare-venv run failed to produce, so
  a "could not collect" in your own prior note is a reason to re-run with the path set, never a
  finding.
- **Prove where a red comes from before you attribute it to the PR: reproduce it on `origin/main`.**
  A board can show five red PRs that share one broken default branch, and holding each of them parks
  work for a defect it does not carry. Check `main`'s last run first, then reproduce:
  ```bash
  git -C "$HOME/repository/git/llgenie" worktree add --force --detach ../llgenie-wt/vmain origin/main
  cd ../llgenie-wt/vmain && python -m pytest --noconftest -q <the modules named in the failing job>
  ```
  Same FAILED set ⇒ the red is **not in the diff**: write "not green, for a reason outside the diff",
  name the two commits that introduced it, and place **no hold** (a hold on such a branch parks it for
  someone else's defect). The unblock is the `main` fix, not a change on the PR. Quote the local
  counts (`4 failed, 66 passed` at the PR head vs `6 failed, 187 passed` on `main`) so the attribution
  is a measurement rather than an opinion. Never fold a shared red into a per-PR verdict without it.
  When the `main` fix itself comes up for review, close the loop the same way: run the **same modules**
  at the fix's head and quote both counts (`6 failed, 187 passed` before → `0 failed, 193 passed`
  after) instead of reading a green job, because a local pass proves the change and only
  `linux / unit` proves the gate.
- **Several PRs failing the *identical* assertions is a shared base, not several authors making the
  same mistake — and `main` passing does NOT mean the diff caused it.** A branch cut before a commit
  that added both an artifact and its index/metadata row fails "missing row" assertions while `main`,
  which has both, passes: the diff looks guilty and is innocent, and the remedy is a rebase, not an
  edit (adding the row in the diff duplicates it on rebase and reds something else). The cheap
  discriminator is a two-sided count, before any verdict — run it, never eyeball it:
  ```bash
  python3 scripts/pr_watch.py --changes-index origin/main <pr-head-sha> [<more heads…>]
  # origin/main   wiki=223 notes=223 preflight=yes base=7db4ac99 verdict=indexed
  # a9fe2fc9      wiki=222 notes=221 preflight=no  base=5a367d42 verdict=SHORT by 1 note(s)
  # 2bf9483f      wiki=210 notes=0   preflight=no  base=0ddfda8b verdict=MISSING-DIR (…rebase, do not hand-add)
  ```
  It prints `indexed` / `SHORT by N` / `MISSING-DIR` / `EXTRA` plus the merge-base per ref, so one call
  classifies a whole sweep: `MISSING-DIR` means the branch predates `docs/changes.d` entirely (rebase),
  `SHORT by 1` is the single missing-note shape, and equal counts on a branch but red on `main` means the
  red is real. Its fixture form is `pytest -q scripts/test_pr_watch.py`. Fall back to the raw loop only
  when the script is unavailable:
  ```bash
  for r in origin/main refs/remotes/origin/pr<n>; do
    printf '%s notes=%s rows=%s\n' $r \
      "$(git ls-tree -r $r --name-only | grep -c '^agent-wiki/.*\.md$')" \
      "$(git ls-tree -r $r --name-only | grep -c '^docs/changes.d/.*\.md$')"
  done
  git cat-file -e refs/remotes/origin/pr<n>:docs/changes.d/<expected>.md && echo present || echo absent
  ```
  Equal counts on `main` + one short on the branch + the file absent on the branch ⇒ **stale base**: say
  "rebase, don't edit" and place no hold (a rebase needs no issue). Getting this wrong is a retraction-
  worthy error in the direction that accuses an innocent PR, so run the count *before* writing the
  verdict — and when you have already written it, retract on the PR with the two numbers, saying which
  of your own inferences was wrong, rather than quietly appending a correction.
- **Measure a per-PR delta against the PR's OWN base (or the API's `files` patch), never against a
  moved `live/main` tip — a stale base shows the inverse of everything that landed after the branch
  point, and reads as the PR carrying foreign files.** Diffing `live/main-tip..head` on a branch cut
  before several merges reports every file those merges added as *removals* in "your" diff (measured
  10 files / 294 deletions where the true PR was 4 files / 49 insertions). The authoritative per-PR
  content is GitHub's own patch:
  ```bash
  gh api "repos/<o>/<r>/pulls/<n>/files" --paginate --jq '.[]|select(.filename=="CHANGES.md")|.patch'
  git diff "$(git merge-base <live-main> <head>)" <head> --stat   # per-PR, not tip..head
  ```
  A **foreign-looking row** in that patch (a `docs/changes.d`/`CHANGES.md` row for a different issue
  that belongs to an already-merged PR) is usually **base-carry, not a duplicate**: the branch snapshot
  predates the row landing on main, so the row rides in byte-identically and the merge is a no-op there.
  Discriminate with the row's bytes, not a read — identical md5 on head and on live main ⇒ carry
  (no-op merge, note-only, **no red, no hold**); different md5 ⇒ a real duplicate the PR introduces.
  ```bash
  git show <head>:CHANGES.md | grep '<slug>' | md5sum
  git show <live-main>:CHANGES.md | grep '<slug>' | md5sum   # equal ⇒ base-carry
  ```
  When a *local* ref disagrees with the API (`git merge-base --is-ancestor` says a sha is an ancestor
  yet `git show <that-sha>:<file>` lacks content the API shows both places), the local object is stale —
  trust the API's tree over the local object and say so; do not build a finding on the stale copy.
- **A fix that greens previously-red tests must CORRECT the assertion, not delete it — read the test
  diff before you say "fixed".** Deleting or loosening the failing assertions turns the board green
  and the change wrong: those assertions are usually the correct alarm for an incomplete code change
  (a group of jobs removed from CI, but three of six test files reconciled). The correction shape is
  an assertion that still fails if the defect comes back — `assert callers["macos"] == (...)` becoming
  `assert "macos" not in callers` is fine; a deleted block, an added `xfail`/`skip`, or a widened
  `except` is a waiver. The same test applies to a repo rule the diff broke (an inline `python3` in a
  workflow `run:` step): satisfying it means moving the work into `scripts/` or a make target and
  calling that, never editing the rule's own test to permit it. In the verdict say which it was —
  "the six went green because each assertion was updated to the new contract and still reds if the old
  shape returns" — because "tests pass" is exactly what a deleted test also reports.
- **A dedup/normalization change that EMPTIES an invariant reds tests while `main` stays green — that is
  the diff's red, not a shared base.** Removing the last member of a class (the last duplicate canonical
  rule, the last of a roster, the last shard) trips assertions of the form `assert names` ("report must
  name at least one …") that were written when the class was non-empty. The docstring may even say the
  removal is the owner's call — that does not update the test. Discriminate exactly: read the job log for
  the `AssertionError` line, then run the same module at `main` (green there ⇒ own-diff, because a green
  `main` is what proves the red came from the branch). The remedy goes in the SAME change set — assert the
  clean invariant, or inject a synthetic fixture so "name it when present" survives without real-tree
  dependence — never dismiss it as shared base just because `main` is green.
- **Check that a fix issue's acceptance command is the command CI actually runs.** An issue scoped to
  one module (`pytest tests/test_x.py -q`) can be satisfied while `make ci-unit` stays red — so every
  PR remains unmergeable and the lane has spent a push for nothing. Add the widening as a comment on
  the issue (all failing modules, then `make ci-unit` exit 0, then a completed `linux / unit` run quoted
  with its id) rather than silently reviewing against a criterion that cannot close the gate.
- **`gh api …/actions/jobs/<id>/logs` reads EMPTY through `--jq .` and errors on escape sequences
  without the flag — redirect it raw, never pipe it.** The log body is not JSON, so `--jq` returns 0
  bytes and the empty file reads like "no log"; without `--allow-escape-sequences` the call fails
  `the response contains terminal escape sequences`. The working read is
  `gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences > /tmp/job.log`, then grep the
  file. Enumerate the failing step first
  (`gh api …/jobs/<id> --jq '.steps[]|select(.conclusion=="failure")|.name'`) so you read the right
  step, and grep the saved log for `AssertionError|FAILED` lines rather than paging 60 KB.
- **Removing a worktree the terminal is cwd'd into breaks every later call — the persisted shell cwd
  points at a deleted dir, so commands fail with a misleading
  `cd: … No such file or directory` (reported as exit 126 / "not executable").** `git worktree remove`
  does not move the shell out of the tree. `cd` back to the main clone, or pass
  `workdir=$HOME/repository/git/llgenie` explicitly on the removing call and on every call
  after it.
- **Build a comment body in a file, and read the published body back — not the post's exit code.** A
  `gh api … --jq "…\"$var\"…"` nested inside a double-quoted shell string collapses silently: the
  comment publishes with an empty field where the evidence should be, and `gh pr comment` still exits 0.
  Write the body with a heredoc into a file, post it with `--body-file`, then read back what landed
  (`gh pr view <n> --json comments --jq '.comments[-1].body'`); run any `--jq` that embeds shell
  variables as its own command and let Python do the formatting. **Quote the heredoc delimiter**
  (`<<'EOF'`, not `<<EOF`): an unquoted body expands every backticked span and `$var` as command
  substitution, so the published comment silently loses `fail=0` and `` `pipeline.yml` `` where the
  evidence should be. When one slips out, `PATCH /repos/<o>/<r>/issues/comments/<id>` with the corrected
  body and re-read it — note that `gh api … --jq .body` emits **raw text**, not JSON, so a `json.loads`
  round-trip fails; treat it as a string. A comment that renders a blank number
  is worse than no comment: it reads later as "nothing to report". When one does slip out, post a
  correction at the same sha naming the error and the real value rather than leaving the blank field
  standing.
  **Post the comment as its OWN tool call and confirm its id landed — a post batched with read-only calls
  can be vetoed and never execute.** A per-turn guard that demands a task-relevant mutation can drop a
  whole batch that mixes reads with the post, and no error surfaces on the post itself; the next
  `gh api …/issues/<n>/comments --jq '[.[-3:][]|.id]'` still ends at the previous comment. Issue
  `gh pr comment <n> --body-file <f>` alone, then read the id list back and confirm the new id is present
  before reporting the verdict as posted — a status line claiming "posted" without the id in that list
  is a claim about intent, not a mutation.
- **`gh run list --commit <sha>` lags a fresh push; the API does not.** Minutes after a push it can
  report no runs for a sha that already has three, which reads as "CI never triggered" and invites a
  bogus empty commit. Ask the API instead:
  `gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>&per_page=10" --jq '.total_count, [.workflow_runs[]|"\(.id) \(.name) \(.status)/\(.conclusion)"]'`.
- **`gh issue view --json` has no `timelineItems` (nor `merged`) — enumerating a wrong field prints the whole available-fields list, which reads like a broken command.** For a close-event timestamp use `--json closedAt,closedByPullRequestsReferences`; for `## Acceptance criteria` state read `.body` and grep the checkboxes. **`gh api … --jq .body` emits raw text, not JSON**, so it never round-trips through `json.loads` — treat every such read as a string.
- **`gh pr view --json` field names are not `merged` — there is no `merged` boolean; ask for `state`, and `mergedAt`/`mergedBy`/`mergeCommit` are the merge facts.** `gh pr view <n> --json merged` errors `Unknown JSON field: "merged"` and prints the whole available-fields list, which reads like a broken command rather than a wrong field. A merged PR answers `state=MERGED` plus non-null `mergedAt`; read those two together (`--json state,mergedAt,mergedBy,mergeCommit`) instead of a boolean that does not exist.
- **`gh api` speaks REST field names; `gh run list --json` speaks CLI field names — mixing them returns `null`, not an error.** A REST run object carries `id` and `head_sha`; the CLI's `--json` shape carries `databaseId` and `headSha`. So `gh api repos/<o>/<r>/actions/runs/<id> --jq '{databaseId,conclusion}'` prints `{"databaseId":null,…}` while the run is perfectly live — the null reads as "no such run" and invites a bogus re-dispatch. Read the run you queried with `id`/`head_sha`; use `databaseId`/`headSha` only on `gh run list --json` output. Likewise `commits/<sha>/check-runs` returns an OBJECT holding a `check_runs` array, so iterate `.check_runs[]`, never `.[]` (which errors `cannot iterate over: number` and hides the real job states).

  One API call, both facts, for a fresh head:
  ```bash
  gh api "repos/<o>/<r>/actions/runs?branch=<ref>&per_page=10" \
    --jq '.workflow_runs[] | select(.head_sha=="<sha>") | "\(.id) \(.status)/\(.conclusion) | \(.name)"'
  ```
  A superseded head shows its old runs as `completed/cancelled` after a force-push — those are `no verdict` at the OLD sha, so filter on the NEW `head_sha` before saying anything about the branch.

- **A fork PR head is not a commit in the base repo's object DB — `commits/<sha>/check-runs` answers `422 No commit found for SHA` and `actions/runs?head_sha=<sha>` answers `total_count: 0`, and both read as "no runs" when the PR is fully covered.** This repo's PRs push from `fork` (`andyholst/llgenie`), so the head sha lives on the fork and a base-repo commits/runs lookup cannot resolve it; the 422/zero is a resolver gap, never a verdict. The one call that resolves check-runs for a PR head regardless of where the object lives is `gh pr checks <n> --repo <base>` — make it the primary read, and reach for the raw `commits/<sha>`/`actions/runs` APIs only with a sha you know is on the base (`origin`/`main`). When you need the object itself for `git show`/`git cat-file`, fetch it explicitly: `git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>` (the explicit refspec works where a bare fork-sha fetch errors `upload-pack: not our ref`). Judge only the rows `gh pr checks` returns for the head `gh pr view` names: a prior head's `CANCELLED` unit leg describes the old sha, not the live one. And a peer's earlier "all checks green, CLEAN" is a snapshot — re-read `gh pr checks` at the live `headRefOid` before agreeing: a still-`pending` leg is no verdict and `mergeStateStatus` reads `UNSTABLE`, not `CLEAN`.

- **A newly added text/markdown file must end with a trailing newline, or `lint_linefeeds` reds the docs gate.** A byte-copy taken from a live profile file can lack one, and the scope job fails with `lint_linefeeds` naming YOUR new file — so the red is the diff's, not the shared base's. Check a file's last byte with `tail -c1 <file> | od -An -c` (`xxd` is not always installed; `od` is); a last byte that is not `\n` (a `.`, `|`, any glyph) is the violation. Fix is appending the newline to the display copy, not editing the lint. Run the local `make lint`/`check-docs` over the exact branch before pushing any docs+skills change so this never reaches CI.

  **A peer's "my local lint comes back clean on the same tree" does not contradict a CI red — the local tree is usually at the base, where the diff's new files do not exist.** The gate runs against the branch head/merge ref (patch applied), sees the new `agent-wiki/*.md` and `docs/changes.d/*.md`, and reds on them; the local `lint_linefeeds.py` over an un-patched working tree never loads them. To answer "name the exact file", read the job log, not the tree: the `scope` job prints `LINT FAIL — files missing a trailing newline:` then a bulleted list of paths, which IS the answer. Get the log via the **correct job id** — `gh run view <run> --log-failed` picks the first failing job in the run and can return `log not found: <a different job id>` when `scope` carries the finding but another job (`ci-verdict`) failed first; enumerate with `gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|{id,name,conclusion}'`, take the `scope` job's id, then `gh api repos/<o>/<r>/actions/jobs/<jobid>/logs --allow-escape-sequences`. Confirm each named file at the head with `git show <head>:<path> | tail -c1 | od -An -c`.

- **`check-pr-authors` has no check name of its own — it runs inside `linux / unit`.** So
  "every listed check is green, the rest are pending" says nothing about attribution. Run it
  yourself on every PR, over the PR's own range:
  ```bash
  python3 scripts/check_pr_authors.py check --base origin/main --head HEAD
  ```
  A commit authored `Asimov Agent <agent@asimov.invalid>` (or `asimov-agent`,
  `github-actions[bot]`, `Hermes Agent`, …) is outside the allowlist and reds the unit job;
  only `Andy Holst <andy.holst@protonmail.com>` and `Asimov Agent <support@docondee.com>`
  are allowed, name AND email. Repair is the gate's own prescription and rewrites no work —
  `git commit --amend --no-edit --reset-author` (author+committer set to the allowed pair),
  `git push --force-with-lease` on the PR's own branch, then prove the tree did not move
  (`git diff <old> <new>` empty) and re-run the check for `OK`. A whole agent fleet can share
  one bad git identity, so check every PR in a batch before believing any of them is green.
- **An author-gate red naming commits that are not the PR's is a range bug, not a rebase.** When CI's
  `guard`/`check-pr-authors` fails and the named shas are `main`'s own merges, do not tell the lane to
  rebase — rebasing onto the newer base is exactly what pulls those commits into the scan. Reproduce the
  **CI shape** and the **PR's own shape** side by side:
  ```bash
  git fetch origin refs/pull/<n>/head refs/pull/<n>/merge
  # CI: PR's recorded base sha .. the merge ref (a pull_request head IS the merge commit)
  python3 scripts/check_pr_authors.py check --base <pr-base-sha> --head refs/pull/<n>/merge   # reproduces the red
  # the range the PR actually owns
  python3 scripts/check_pr_authors.py check --base origin/main   --head refs/pull/<n>/head    # usually OK
  ```
  `ci.yml` passes `PR_BASE = github.event.pull_request.base.sha`, so `<base>..<head>` sweeps everything
  the base branch gained after that sha. The fix is the range start (`mb=$(git merge-base "$PR_BASE" "$PR_HEAD")`),
  which is what `check_pr_authors.py`'s own docstring claims the scan is. Also check the default branch
  before blaming any PR — `git log -6 origin/main --format='%h %an <%ae>'` and
  `--base <old-tip> --head origin/main`: a missing surname there is enough to red every PR at once, and
  re-authoring `main` is a history rewrite that stays the owner's call.
- **A `docs/changes.d/<x>.md` fragment must link an `agent-wiki/<name>.md` note that exists on the
  SAME branch — `check-docs` reds otherwise, and it catches it before you can commit.** The fragment is
  a one-row index entry whose `Record` cell points at an `agent-wiki/` note; `changes-index` asserts that
  note is present, so creating a fragment on a branch that does not carry the note (e.g. you draft a
  change-record on the reviewer's own branch but the note lives only on the PR-under-review's branch)
  fails with `[changes-index] ERROR: docs/changes.d/<x>.md: links agent-wiki/<name>.md, which does not
  exist`. Always run `make check-docs` (or `make changes-index`) over the exact branch before committing
  the pair — a fragment with a dangling note reference is a red gate, not a record. When the note lives
  on another branch, either add the note here too or do not create the fragment; never leave a
  note-less fragment behind. The link target must be `agent-wiki/<name>.md` or `./agent-wiki/<name>.md`
  — the gate's regex anchors on that prefix, so `../agent-wiki/<name>.md` (the natural path when the
  fragment sits in `docs/changes.d/`) fails the link check even though the file exists on the branch.
  Write the path relative to the **repo root**, not to the fragment, and re-run `make check-docs` after
  fixing a `../` link.
- **When your local branch has diverged from the fork ref you mean to update, push to a DISTINCT branch
  — never force over a shared/foreign branch lineage.** A reviewer's record commits often build on
  `main`'s history while the fork branch (`fix/…`, `reports/…`) still carries the earlier review-record
  lineage, so `git push fork <branch>` is rejected non-fast-forward and `--force` would discard the
  remote lineage. The safe move is `git branch <new-name> HEAD && git push fork <new-name>` — a fresh
  ref that carries your commit without rewriting anyone else's — then verify with
  `git ls-remote fork refs/heads/<new-name>`. Confirm ancestry first (`git merge-base --is-ancestor
  <remote-sha> HEAD`); if it is NOT an ancestor, they diverged and a force is the wrong tool.
- **A `pull_request`-triggered gate reads the PR body snapshotted at event-fire — re-running the same run id can NEVER clear a stale-body red; only a fresh `pull_request` event does.** `ci.yml` passes `PR_BODY: ${{ github.event.pull_request.body }}`, which is frozen into the stored event payload when the run is created. Editing the body afterwards and re-running (`gh run rerun`) re-reads the OLD body forever, so the gate reds identically and reads as "the fix did not work". Discriminate before blaming anyone: compare the run's `created_at` (from `gh api …/actions/runs?head_sha=<sha> --jq '.workflow_runs[]|.created_at'`) against the body's `updatedAt`. If every run at the head fired BEFORE the edit and the gate passes locally against the current body (`check_pr_closing.py check --body-file <current> --rev HEAD` → rc=0), the red is a snapshot artifact, not a tree defect. The only remedy is a **fresh `pull_request` event at the same head** — close+reopen by the owner, or a no-op commit — never another re-run and never an amend the squash text does not need. Same class as the CANCELLED rule (a cancelled/superseded run is no verdict, needs a fresh run at a frozen head), but here even a fresh run of the SAME event is insufficient: the event payload itself must be re-fired.
- **`check-quant-catalog` reds every PR when the live Hub search changes** (issue #769).
  Do not let an author fold that data regeneration into a feature/docs PR; it is its own
  change.
- Merge order matters: a docs census refresh and a PR that adds files cannot both be
  "current" — land the code PR first, then regenerate the census.

## Sweeping many red PRs in one pass

When the ask is "review every failing PR" rather than one dispatch, do not write and post each comment by
hand — the boilerplate drifts and one malformed body survives unnoticed:

**When the ask is *rebase every open PR* onto a moved `main`, not review — see
`references/rebase-sweep.md` for the per-PR order (head re-read via API, merge-base skip, the
`CHANGES.md`-regenerate conflict fix, the `--continue`-hang recovery). The one rule that decides a
whole sweep is decided BEFORE any push: a PR's head may live on the fork (`head.repo.full_name` =
`andyholst/llgenie`), and pushing its rebase to `origin` updates no PR while creating or wrecking a
same-named branch on the base repo. Read the head repo from the API and push to `fork` when it is the
fork; also note the PR-head API lags a fresh force-push (verify with the ref read, not the pull
object), and a `do-not-merge` label is left untouched through the rebase.**

1. **One evidence call per PR, batched.** `gh run view <id> --log-failed > /tmp/prlogs/<id>.log` for every
   failing run, then extract the failing test *lines* from the files
   (`grep -oE 'tests/[a-z0-9_]+\.py:[0-9]+: AssertionError' | sort | uniq -c | sort -rn`). Read the counts,
   not the whole 400 KB log — a repeated identical assertion 80 times is deterministic, not flake.
2. **Classify with one command, not per-PR prose.** `--changes-index` for the index family; for anything
   else compare against `origin/main`'s last **completed** CI run and say the sha it belongs to.
3. **Generate the bodies in Python, post with `--body-file`, read every one back.** A dict per PR
   (`n`, `sha`, `run`, failing lines, attribution line) fed through one template keeps the four required
   facts (sha, command, run id, `auto=none`) identical everywhere; then loop `gh api …/issues/comments/<id>
   --jq .body` and assert each contains its own sha and `auto=none`. Posting exit codes prove nothing.
4. **Report the grouping, not just the rows.** "N PRs, one missing note" is the finding a dispatcher can act
   on; N separate verdicts with no shared sentence is homework.

Mixed heads are normal and must be said: a PR can carry the shared-base failure **and** one of its own
(`CHANGES.md is out of date` plus two `test_engine_skills` assertions). Name both families and give the
rebase for the first, the code question for the second.

## Verdicts

- **Request changes — `gh pr review -r`** — a factual claim in the diff or body is false (stale census,
  a gate that does not do what it says), a gate is red for a reason the diff caused, the diff is out of
  scope, or secrets/permissions weaken. Post as a REQUEST_CHANGES review naming the failing acceptance
  criterion, the head sha and the run id (issue #1193) — a verdict the merge gate and the owner can read
  at a glance, not a body-only comment.

**When the head's author IS this lane's own login, GitHub refuses the verdict state** — `gh pr review -r`
(and `-a`) error with `Can not request changes on your own pull request` / `Can not approve your own pull
request`. In this clone the reviewer token and the PR author are the same identity, so a load-bearing
`-r`/`-a` is simply unavailable from this seat. Do **not** fabricate an approval or narrate a comment as
if a review state were posted.

**The one formal-review state that IS available is `--comment`.** `gh pr review <n> --comment --body …`
succeeds even on your own PR and records a real review object under `reviews/` (state `COMMENTED`, your
login, the head `commit_id`) — distinct from a body-only `gh pr comment`, which never appears in
`reviews/`. Prefer `--comment` over `gh pr comment` for the fallback: it puts the verdict into the formal
review list a merger scans, and costs nothing the `-a`/`-r` would have. **But a COMMENTED review does not
flip `reviewDecision`** — the gate stays `REVIEW_REQUIRED` until a *distinct* identity posts an APPROVE.
Verify with `gh api repos/<o>/<r>/pulls/<n>/reviews --jq '.[]|{state,user:.user.login,commit_id}'` and
`gh pr view <n> --json reviewDecision`: a COMMENTED-only history with `reviewDecision=REVIEW_REQUIRED` is
the honest state, not a failure of your post. The formal APPROVED that clears the gate is another
identity's to grant (a fleet bot login, or the owner's) — route it to the planner with the try-it-live
evidence below rather than claiming the gate is yours to close.

**Prove the identity block live before answering "formal review or out of remit" — do not answer from
memory.** One call settles which states this seat can and cannot post at the current head:

```bash
gh pr review <n> --repo <r> --approve --body "probe" 2>&1 | head -1   # expect: Can not approve your own pull request
gh pr view <n> --json author --jq .author.login                          # expect: your own token's login
gh api user --jq .login                                                 # equal ⇒ the block is real, cite it
```

That pair (`author == my login`) is the mechanism: GitHub forbids an author approving their own PR, so no
verdict state above COMMENTED is available here. Report it as *"`-a` mechanically blocked, `--comment`
posted, formal APPROVED is the distinct identity's"* with the exact error string — that is a measurement,
not a refusal.

**An `APPROVED` review sitting on a head whose deciding leg has since failed is board state to flag, not a
green.** `reviewDecision=APPROVED` while `mergeStateStatus=UNSTABLE`, where the approving review's
`commit_id` equals a head whose `linux / unit` (or other deciding) run has failed, is the
self-stamped-approval-on-red pattern. Report the approving login, its `submitted_at`, and the red run id,
and treat the approval as **no verdict** — never cite `APPROVED` as evidence the criteria were met at that
head. Correcting or dismissing it is the owner's/planner's call unless a hold is already in place.

**A distinct-identity `APPROVED` (the auto-merge bot login) sitting on a GREEN head you are about to review
is not your verdict and must never be adopted as one — flag it and keep your own state honest.** When the
review list shows `{"state":"APPROVED","user":"<automation-login>"}` at the head *before* your `COMMENTED`,
that is the self-approval class (#491/#1088) whether or not the deciding leg is green: your review posts
`--comment` (author==your login blocks `-a`/`-r`), and you report the stray APPROVED — its id, login,
`submitted_at`, head sha — to the planner to fold into the #1088 evidence set, exactly as for a red-head
stamp. Do not delete it, do not cite it as evidence the criteria met, do not narrate it as your own.
- **Approve — `gh pr review -a`** — every acceptance criterion is verified green with only non-blocking
  notes (doc omissions, nits, merge-order advice). Post as an APPROVE review with the same evidence
  anchor (head sha + run id or exact test command). This is the load-bearing good verdict (#1193); the
  `-a` is a statement the criteria met at that head, never a merge this lane performs.
- **Nothing** — a PR whose head sha, checks and review state you already reported and that has not
  changed.

**Current-head green gate (owner escalation 2026-11-04, filed in `agents/standing-rules.md`).** A PR is not "handed to CI" — the lane that opens it owns its pipeline until every required gate is green at the CURRENT head sha. A mid-green PR (one gate red, some still running) is a parked lane, not a done lane (#1705 pattern). For the reviewer: when you review a PR that is NOT fully green at the head, say so explicitly in the review — which gates red, at which sha — and do not approve/co-sign until a fresh run at the CURRENT head confirms green, not the stale head a fix-then-body-edit left behind. **A body edit does not re-trigger CI: the check still evaluates the pre-fix body.** Quote the current head sha with your green, never a stale one.

**Post the verdict at the PR's LIVE tip, not the sha you started polling — the head moves under you while the suite runs.** A ~12-minute `linux/unit` leg is long enough for the owning lane to push the fix you just asked for: you poll the run at `X`, it concludes FAILURE, and a NOT-GREEN posted at `X` grades a *parent* the tip already passed, which will never turn green and which the planner must spend a turn correcting. One read immediately before posting settles it, and it must be in the same breath as the post:

```bash
gh pr view <n> --repo <r> --json headRefOid --jq .headRefOid   # must EQUAL the sha you judged
```

If it differs, the run you measured is a superseded-head result: re-fetch the new head into a worktree (`git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>`), verify the diff between the two shas is exactly the fix you prescribed, re-run the deciding leg at the new head (local gate + poll its fresh run), and grade *that*. Say in the verdict which shas were superseded and why ("`<old>` NOT GREEN, run `<id>`; `<new>` GREEN, run `<id>`") so the board reads the history rather than one verdict floating on an abandoned commit. A NOT-GREEN at a superseded sha is never "the fix failed" — it is the completed verdict of the pre-fix state.

**A verdict is about a sha, so it expires; a cause is not, so post that once on the umbrella.**
When every head in a family has moved past the shas you read, do not post a late verdict dressed as a
review — freeze one head and judge it, or say nothing. What does not expire is the shape of the failure:
"these branches are short one index note against `main`'s count, merge-base `<sha>`, remedy is a rebase"
is true of any head that kept that base, so it belongs on the tracking issue and each lane can act on it
without a fresh measurement from you. Post the cause on the umbrella issue, the verdict on the PR, and
never the other way round.

**A gate-fix PR that proves its case by QUOTING a close keyword can red on its own proof text.** When a PR under review describes the very hazard it fixes (e.g. umbrella-close-guard proof body quoting `(closes #1812)` as the measured example), the keyword-naive `check-pr-closing` parse treats the quoted example as a real close: the squash set `{1812}` then disagrees with the body set `{#1815}` and the PR's required gate reds on itself. As reviewer, grep the PR's OWN commit + body for close-keyword adjacency before judging green: `git show -s --format='%B' HEAD | grep -inE 'closes #[0-9]|fixes #[0-9]|closed #[0-9]'` and compare the squash set to the body's `closing_references`. A head whose tree is byte-identical to a reviewed sha but whose commit/body text was rewritten (force-push, same tree, message-only) changes the *wiring verdict* (close sets, `check-pr-closing`) without touching the logic — re-anchor the citation to the new sha rather than re-reviewing the code, and scan any later PR body that quotes your earlier verdict text before judging it, since that quote can re-trip the same parse.

When a peer lane says "re-measure from `<head>`, your finding does not reproduce here", **do it before
you defend it.** `git ls-remote origin refs/pull/<n>/head`, re-run the exact gate/check at that sha, and
if it is now green the finding was correct at the sha you read and is history — retract on the PR naming
BOTH shas (`stale-shas → current-head`, which one was wrong), never append a softening, and never let a
snapshot you no longer own stand where a lane will re-read it. A blocker list is a claim about a tree,
and a tree that has been repaired since your measurement is the one the current head describes. This is
the same re-measure in the direction that clears your own finding, instead of accusing a PR of one.

A green PR that still cannot move is a **defect in the merge path, not on the PR**: if
`mergeable=MERGEABLE` and the required run concluded green but `mergeStateStatus` stays `BLOCKED`
on `REVIEW_REQUIRED`, the approve step or its gate is at fault — report it against the automation's
own issue, and post the green verdict as `gh pr review -a` per #1193 so the board records that the
criteria were met at that head, without this lane merging anything. Equally, never derive "green" from
a job count that is still moving: a run with rows queued or in progress has no verdict, and the pending
row is often the deciding one. **When the deciding leg is merely `in_progress` (a long suite, ~12–14 min),
poll it to a conclusion rather than stopping:** get the job id from `gh api
repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|select(.name|test("unit"))|.id'`, then loop `gh api
repos/<o>/<r>/actions/jobs/<job> --jq '"\(.status)/\(.conclusion)"'` with a ~25s sleep and a bounded count,
breaking on `completed`. A `completed/success` at the head is then a real verdict to cite; stopping
at the first `in_progress` reads as "no verdict" when the leg would have concluded a few minutes later. Only
the *absent* run (queued, never started) is "no verdict, stop" — an *advancing* one you wait for.

**Size the loop to the call cap, not to the job — a killed poll is not a failed conclusion.** A foreground
terminal call is killed at roughly 420 s of wall time even when a larger `timeout` is requested, so a
`18 × 35 s` loop (630 s) dies mid-poll and the error reads like a tool failure rather than "still running".
The cap catches loops that look modest too: `18 × 25 s` (450 s) is still over it and was killed in
practice, so count iterations, not just the sleep. Keep each poll call at ~12–15 iterations × 25 s
(≈ 300–375 s), expect to re-poll once for a ~12–14 min unit leg (the second `for i in $(seq 1 12)` call
usually sees `completed/success` on the first ticks), and treat the killed call as *no information*:
re-issue the same loop from the current state, never re-run CI or push to "get a fresh run". A unit leg that started before your first poll will have advanced
when the second call opens.

## Evidence block to include in every review

Numbers and exit codes, from your own run: the gate command + exit code, the failing or
absent engine/cell names, the test count, the doc gate line (`[check-docs] ok: …`), and the
CI verdict with the run id. Quote `gh` output, never paraphrase "CI looks green".

**When you need to prove a multi-part finding (or clear the nerve guard's "verification has not
passed"), run one executable claim script rather than a series of prose reads:** `templates/finding-verification.py`
is a copyable harness — replace its CLAIMS section with the finding's assertions against fresh `gh`/file
reads, run it, and quote `RESULT: ALL VERIFIED` + exit 0. Exit 1 names the failure. It is evidence a
reader can re-run, not churn to appease a heuristic.

When the verdict is going to a merger, make it one sentence they can act on, either way:

```
green at <sha>, run <id>, N success / 0 failure / 0 cancelled, mergeable
either: not green, because <job> failed at <sha> in run <id> — <cause or "cause unreadable while in progress">
```

`cancelled` counts are part of that sentence, never omitted: a cancelled row is the difference between
"verified" and "no verdict", and a merger reading only success/failure cannot see it.

## Scheduled watch

`scripts/pr_watch.py` in this profile prints a deterministic fingerprint of every open PR
(head sha, review decision, merge state, labels, check buckets, comment count, the latest review
as `reviewer=<login>:<STATE>@<date>`, and the newest run at the head as
`runs=<wf>:<id>:<status>/<conclusion>|…` — every run at the head, because a verdict must cite the
`CI` id *and* the `scope`/`docs` ids beside it, so none of them has to be looked up by hand). Use it as a cron `monitor` script so
the agent is only woken when something actually changes; a diff in its output is the
trigger. It deliberately ignores *who* commented, so a hold that disappeared shows up as a
`labels=` change — and it prints

    WARN: APPROVED with no do-not-merge hold by <login> — verify a human made it
    ACTION: failing and unheld by <login> — review it or place do-not-merge with a reason
    UNVERIFIED: 0 checks and no run at this head — a non-main base gets no workflow, …
    NO VERDICT: the CI run at this head ended cancelled — …needs a fresh run at a frozen head, not a fix

when an approval exists without the hold, which is exactly the shape of an agent approval
under the owner's token. Prove the guard without waiting for a real incident:
`python3 scripts/pr_watch.py --selftest` (fixture checks, exit non-zero on failure).
The selftest also exercises the tree-side checks without needing a checkout: it swaps in a fake
`git` and asserts `--changes-index` marks a `docs/changes.d`-absent tree `MISSING-DIR` (never
`indexed`) and that `--soul-shrink` runs with no live profile — so a regression that makes the
discriminator call a clean tree `indexed` reds the selftest, not just the pytest module.

`python3 scripts/pr_watch.py --fingerprint` prints the sha256 of the exact bytes the monitor
hashes, so it can be compared with `monitor_state.last_output_hash` from
`cronjob_manage action=list`: equal ⇒ the next tick is skipped, different ⇒ the state really
moved. **A hash difference between two runs is not proof the script is flaky** — CI checks
complete between invocations, which is precisely the event the gate exists to catch. Diff the
two outputs (`python3 pr_watch.py > a; sleep 1; python3 pr_watch.py > b; diff a b`) before
touching the script; byte-identical across five consecutive runs on a quiet board is the
determinism proof. Verify the pipeline end-to-end from `cron/executions.db`
(`status`, `delivery_outcome`, `finished_at`), not from the scheduler's promise.
**After you *change* the script, prove determinism over frozen inputs, not over the live board.**
A two-run `diff` on a live board differing is the *expected* non-flakiness case (a check completes
between the ticks), so do not chase it as a regression. The proof that your new argv path is stable
is to feed it the same refs twice and diff those — `--changes-index origin/main <sha>` twice and
`--soul-rules <ref>` twice must both `diff -q` empty with `exit 0`. State that you measured frozen
inputs, and say the live/two-run diff is the documented exception, so a reviewer reading your
verification does not mistake an expected board movement for a broken script.

**A monitor fix is proven by executing the fixed path, not just by its unit predicates.** After repairing a crash class in `pr_watch.py` (a null run id becoming a URL, a `gh` non-zero becoming `SystemExit`), the acceptance is a real run of the entrypoint that shows the killer signature absent — not a green pytest module, which exercises predicates in isolation and never walks the whole tick. Run `main([])` with stderr captured and assert the failure string never appears, plus a clean exit:

```bash
python3 - <<'PY'
import sys, io, contextlib
sys.path.insert(0, 'scripts')
import pr_watch
buf = io.StringIO()
with contextlib.redirect_stderr(buf):
    rc = pr_watch.main([])          # the actual cron entrypoint, full board
err = buf.getvalue()
print('rc=', rc, 'killer_absent=', 'actions/runs/null' not in err, 'gh_abort_absent=', 'ERROR gh' not in err)
assert rc == 0 and 'actions/runs/null' not in err
PY
```

Quote `rc=0`, the absent-marker booleans and the report's first lines in the closing comment. This is the layer between "the predicates pass" and "the cron tick does not abort" — a fix that guards `usable_run_id` but leaves one unguarded path still fails end-to-end while the unit test is green. The incident this closes: a monitor died silently on seven consecutive ticks because the unit-level guard existed in one function but an unguarded sibling path still built `actions/runs/null/jobs`; only running `main()` under `redirect_stderr` showed the abort.

The first three lines are fixed and in this order: `workflows: active=N (names) disabled=M (names)`,
then `main: <sha> CI <status>/<conclusion> [FAILED:<jobs>]`, then the queue. The `main:` line exists
because a PR's red only means something against the baseline it was judged on: one red `main` can make
a whole sweep of PRs look red, and `main`'s own runs get cancelled by successive merges, so read it as
"no completed verdict at the head" when it says `queued`, `in_progress` or `cancelled` — never as green.
When it reports `failure` it names the failing jobs, because "main is red" is useless to a lane
deciding what to fix.

The `workflows:` line is how the fleet pause shows up: the owner disables workflows (20
`disabled_manually` while paused), and nothing else in the
fingerprint moves when that happens *or when it is lifted*, so this line is what makes the monitor
wake on a resume. The **names** are in it deliberately (short slugs, sorted) because "5 came back"
and "the 5 that came back are the ones my work depends on" are different facts; the **delta** is
deliberately NOT in it, because a value depending on the previous run would make two ticks differ on
an unchanged board and fire every tick. The agent diffs this line against its own previous output
(`continuity`) and reports `disabled 20 → 0, came back: auto-merge, fix-bot, …`.
While paused the job is monitor-only: report deltas with run ids, take no action.

`python3 scripts/pr_watch.py --changes-index <ref…>` is the branch/base discriminator described under
"Several PRs failing the identical assertions": it counts `agent-wiki/*.md` against `docs/changes.d/*.md`,
checks the preflight note, and prints the merge-base and a verdict per ref (`indexed` / `SHORT by N` /
`MISSING-DIR` / `EXTRA`). It shells out to `git` through an injectable `git()` so the tests need no clone;
keep that seam when editing it — a test that stubs the wrong argument position passes against a broken
implementation (a fixture reading `args[1]` where the real call puts the path in `args[-1]` reports a
false failure; fix the fixture, never the code it misrepresents). Defaults to `origin/main` with no refs.

`python3 scripts/pr_watch.py --soul-rules <ref>` is the per-lane rule census described under "A rule
stated twice": it counts rules 13/14/15 in every `agents/<lane>/SOUL.md` at the ref and returns one line
per lane with `ok` / `ABSENT` / `DUPLICATED`. Run it before declaring a behaviour-tree PR reviewable —
the gate's regexes pass a duplicated rule, so exit 0 is not evidence that each rule is stated once.

The fingerprint's contract is tested, not trusted: `pytest -q scripts/test_pr_watch.py`
(29 cases — identical state renders identical bytes, a held approval does not warn while an unheld
one does and names the approver, a red `main` names its failing jobs while a cancelled one says
"no verdict", `SKIPPED` is not a failure while `ACTION_REQUIRED` is,
`CANCELLED` is neither a failure nor a verdict, a cancelled CI run at the head raises
`NO VERDICT:` while a green or in-progress one does not, the workflow pause line counts
active/disabled, and `--fingerprint` hashes exactly what the plain run prints).
To measure the whole board rather than one PR (how many open PRs have a cancelled run at their
head, which were never gated at all, and — the other half — which recently merged commits had no
conclusion behind them), use `references/board-sweep.md`: the recipes and the arithmetic that turn
them into a citable number. The same file carries the **delegation census** — one `gh pr list` call
classified into `CONFLICT / RED / NO VERDICT / GREEN`, with the row format a dispatcher can assign
from — which is the right answer when the ask is "which PRs are red or conflicting, and who fixes
them" rather than "review this one".
Run it after any change to the script; a divergence between the printed and hashed
stream would make the monitor lie about whether the state moved.

**Verdict-citability audit (scope 3 of the empty-queue contract, measured 2026-11-02 → filed #1619).**
The #1273 standard is "a merged/reviewed PR carries a citable verdict naming the run id AND the head sha." When the reactive queue is empty, sweep it mechanically instead of eyeballing: `gh pr list --state all` for merged, then per PR `gh api …/issues/<n>/comments` + `…/pulls/<n>/reviews`, regex `\b\d{11,}\b` for run and `\b[0-9a-f]{7,40}\b` for sha. Key discriminator: **the declaring verdict can be the auto-merge APPROVED review body, which is generic text** (`LGTM`, or "Approved by the repo's auto-merge job (issue #491)") — it interpolates neither field, so a green-merged PR can have a non-citable verdict on record. This is distinct from the bot-verdict *marker* `run=` slot (#1556): the APPROVED *body* path was never brought under it. Separate your own lane's verdicts from the audit (mine were 13/13 citable) so the finding names the real owner of the gap, and discriminate the 5 flagged rows before calling them gaps (claim/evidence notes legitimately defer the run id to the verdict). File the finding as a refined six-section `agent:implement` issue (#1197/#1273 route), confirm the label on-record, one line to the planner.

**Close-set completeness audit (empty-queue contract, scope 3, measured 2026-11-02 → filed #1629).**
`check_pr_closing.py` validates that the keywords a PR body DID write are ADJACENT to the ref (`closes #N`) — it does NOT detect a PR whose diff actually fixes issue X while the body names X (numerically) but never grants it a closing keyword. Probe this class: for a merged fixing PR, `grep -o 'closes #N'` the body vs `git show <merged-commit>:<file>` the diff; every issue number the body references that the diff demonstrably implements must be either adjacent-closed or on-record "does not close because <reason>". A descoping issue (#1617 symptom) can be closed while the true root-cause (#1582 guard) is orphaned-OPEN with its fix landed in main. Root cause: the gate checks adjacency of chosen keywords, never issue-set completeness of the change. Reusable: `gh issue list --search "<closes-keyword> in:title"` to rule out a duplicate before filing, and confirm the fixing commit via `git show --stat` on the merge before claiming the issue is resolved. When the dispatch names a reactive PR (#1628), re-read its state first — it may have merged mid-dispatch (moot, no verdict owed) and its generic auto-merge APPROVED body is then evidence for #1619, not a new vehicle.

**Acceptance write-back audit (empty-queue contract, scope 3, measured → filed #1644).** The renderer enforces `## Acceptance criteria` as tickable `- [ ]` items (`scripts/check_issue_body.py`, "a criterion a reviewer cannot tick is not one", #745) — but nothing writes the result back: a PR closed on all-green, with every criterion proved in a reviewer's verdict, leaves the issue's boxes `- [ ]` forever. Probe it: pick a recently-closed issue whose fixing PR was reviewed, `gh issue view <n> --json body,state --jq '.state, .body'`, and count `grep -cE '^- \[ \]'` (unticked) vs `'^- \[x\]'` (ticked); a CLOSED issue with all criteria still `- [ ]` while the merge was reviewer-proved is the gap. Confirm the mechanism with `grep -cE '\[x\]|acceptance' scripts/auto_merge.py` (0 ⇒ no write-back) and that no `PATCH /repos/…/issues/{n}` on the body exists anywhere. The fix is the reviewer's own write-back: on a reviewed-green merge, tick exactly the criteria the posted verdict proved (referencing review id + head sha + run id), leave unproved ones unticked, and an auto-merged PR with no reviewer verdict legitimately leaves all unticked (#1088-class — honest, not a defect). File as a six-section `agent:implement` issue; the approve-chain identity problem (#1088) is a separate open policy issue, explicitly excluded from this finding.

**Filing any audit finding: six-section issue, prior-art first, prove it against the repo's own intent.** Before filing: rule out a duplicate with targeted `gh issue list --state all --search '<phrase> in:title,body'` per phrasing (several unrelated-looking hits that only share words is *not* prior art). Render the body in the exact six-section shape (`## Problem` / `## Why it matters` / `## How we fix it` / `## Benefit` / `## Acceptance criteria` (`- [ ]` items) / `## Technical` last) — a producer that must pass `check_issue_body.py` renders *through* `issue_body.render`, but a hand-filed audit finding writes the same headings in the same order with a dedupe marker on line 1. Write the body with a heredoc to a file and post `gh issue create --body-file` (never a `--body` string that shell would expand), label `agent:implement`, then verify the landing (`gh issue view <n>` shows all six `## ` headings in order) and post the audit-deliverable comment naming the measured sha/PR/issue numbers. Quote the repo's own renderer docstring as the standard the finding is measured against — an audit finding is the tree failing its own stated contract, not a taste call.

**#1619 implementation (planner-routed own-vehicle):** when a finding this lane filed is routed BACK to it to implement (implementer declined), the deliverable is the PR — but the self-review prohibition still holds: post evidence as a comment-only review on that PR, never `-a`/`-r`, never a merge/arm (#1088). The fix bodies: `scripts/auto_merge.py::approve()` interpolates the head sha judged (`state.headRefOid` threaded through `try_approve`) and the deciding run id (`$GITHUB_RUN_ID`) into the APPROVED review text; a PR whose state carries no head sha is never approved. AC#4 citable-guard regression = assert the `pr review --body` satisfies the #1273 sweep regexes `\b\d{11,}\b` (run) and `\b[0-9a-f]{7,40}\b` (sha) and contains the actual run id + judged sha; a no-head-sha state must post no approval and no merge. When a new base CI is broken (a ci.yml run with `total_count:0` jobs = a workflow-load rejection, not a PR defect), confirm with `git show <base-commit>:.github/workflows/pipeline.yml` that the base carries the defect (#1618 GITHUB_TOKEN-under-workflow_call) and that your diff never touches a workflow — then report the deciding unti leg as blocked on the base fix + rebase, and post the evidence comment rather than a verdict.

- **A dispatch can name a PR that is CLOSED the same minute you start — re-read `state` at the FIRST check and stop if it is not OPEN, never after polling/building the verdict.** Measured: #1708 closed (not merged) 18:49:32Z, head_ref_deleted 18:52:22Z; my first `gh pr view` returned `state: CLOSED` and I polled to a green unit, posted a GREEN verdict 19:01:42Z — a ghost-frame on a closed PR, needing a withdrawal comment. The planner's "review this PR" may have been written from an OPEN board snapshot minutes earlier; the PR can close under you between dispatch and your first read. The one read is the `gh pr view <n> --json state` line, taken before anything else (before the checks read, before the worktree): if `state != OPEN` (closed without merge, `merged_at: null`), there is **no head to grade** — record the run facts only as evidence, post no verdict, report the closed-without-merge state back and stop. A closed-not-merged PR is not "no verdict yet", it is "already concluded by its owner — review is moot".
- **A `# proc-allow: <reason>` marker must sit ON the line the proc-gate scans — the `subprocess.run(` opener — not on a wrapped continuation line.** `check-proc-gate` matches "a line carrying `# proc-allow:`"; when the call is wrapped so the marker ends up on the `capture_output=` continuation line, the opener line reads as a bare call site and the gate reds `scripts/<f>.py:<line>` naming only the `subprocess.run(` line. **Two-fold disclosure trap:** (1) a generator that writes `subprocess.run([…], cwd=root,` on line N and the marker on N+1 looks right in the editor but fails the gate; (2) **a defect masked by a later ci-unit red survives a first review** because `make ci-unit`/test-unit stops at the FIRST failing gate — fixing that gate lets the suite progress to a genuinely-second bug that existed from the start. Measured twice in this class: fixing five convention gates exposed a sixth (`check-import-roots`, see the workflow-PR list) that was present in the new test file from the first push, and the unit leg reds at a gate *after* the tests pass (2985 passed, then `check-import-roots`), so a green test count is never a green chain. When a fix turns one red green, re-run the **whole** unit chain before declaring the PR green — and when a fix push lands, expect the next failure to be a masked one; grade it as a new, own-diff defect, not as evidence the fix failed. **A mid-green PR is a parked lane, not a done lane — a fix that is correct but never re-evaluated at a fresh head leaves the PR red (#1705): name the still-red gates + the current sha and hold; "correct" is not "green at the current head", and a body edit does NOT re-trigger CI so the stale-head verdict is meaningless.** Verify marker placement with the gate itself (`python3 scripts/check_proc_gate.py check`) at the head, never by reading the source.
- **A gate that reads the linked issue's `## Acceptance criteria` is BLIND to an issue whose criteria live under a `**`-bold header — measure the issue's heading shape before trusting a green.** `issue_body.section_body` matches only `^## <name>$`, so an issue authored as `**Acceptance criteria:**` (bold, no `## ` heading at all) yields **zero** items: `acceptance_verdict(issue, pr)` returns `[]` → the gate reports `[check-pr-acceptance] OK` (green) on a closes-#N it is supposed to hold, and the write-back seam `acceptance_writeback.tick_acceptance` raises `BodyError: the body has no ## Acceptance criteria section` — so even a posted reviewer verdict CANNOT tick the boxes. Measured on #1792/#1797 (`## headings in #1792: NONE`; gate + tick both green/fail as described). When a dispatch premise says "X reds a gate because the issue is unticked", do not assume the gate sees the issue's boxes: run the real gate against the live issue body AND `acceptance_writeback.tick_acceptance` against it, and check `python3 -c 'import re,json;[m.group(1) for m in re.finditer(r"^##\s+(.+?)\s*$", open(F).read(), re.M)]'` on the issue body for a canonical `## ` heading. A verdict-gated write-back (#1644) is only ever reachable on a canonical-`##`-headed issue — when bold-headed, get the body re-rendered (fix B), drive the seam from your accepted COMMENTED verdict: `python3 scripts/acceptance_writeback.py writeback --issue <N> --proven 1..K --verdict-ref 'reviewer=<self> comment=<id> head=<sha> run=<run>' --repo asimov-agent/llgenie` (dry then live), verify = `gh issue view <N>` shows all `- [x]` + updatedAt moved. Confirmed on #1792: verdict comment 6661591003 → write-back PATCHED 6/6 (15:15Z) → `acceptance_verdict(ticked issue, closes-PR)` = 0 findings (gate clears); re-measure head CI on a fresh run after the tick. **A comment does NOT auto-trigger a rerun — but when it IS re-run at the same head, the acceptance gate re-reads the issue body LIVE (`check_pr_acceptance.py`: "The issue body is read LIVE (`gh api repos/<o>/<r>/issues/<n>`) at merge time — the merge-tip measure, never a cached copy") and the PR body LIVE (`ci.yml`: `PR_BODY="$(gh api .../pulls/$PR_NUMBER" --jq '.body // ""' ...`)"` — "NOT an event snapshot, so a body-only fix clears on rerun"), so `gh run rerun <id> --failed` at the SAME head IS the honest re-trigger and re-reads criteria 1+3 → the gate drops to only the still-unticked designed hold. It is NOT event-bound, and no push/regraft/new pull_request event is owed for an issue-side or body-side tick. Measured on #1820: write-back ticked #1818 1+3, rerun of 42148365235 read LIVE body → `[check-pr-acceptance] 1 violation` (only criterion 2, the designed post-merge hold), down from 3. When a peer (or my own report) says a write-back "wont clear until a fresh PR event", that is a stale-snapshot misconception — verify by reading `scripts/check_pr_acceptance.py` (docstring verbatim) and `ci.yml` before re-posting it.
- **When a PR has several `guard` check-runs of the same name, only ONE is the acceptance-bearing row — read each job's step list before reporting the acceptance step green (or red).** Three guard rows can register on one head: a trigger/owner-guard row and a checkout-only row carry `Set up job` / `Owner or collaborator trigger guard` / checkout, no make steps; the row that actually embeds `make check-pr-acceptance` (+ `check-pr-closing`, `check-pr-authors`, `check-pr-agents-line`, `check-pr-sync-line`, `check-pr-base`) is the one that proves the acceptance gate. On #1797@05724a17c only guard check-run 127334830552 listed `make check-pr-acceptance` = success; the other two were scaffolding. Read `gh api …/actions/jobs/<id>` steps, never assume the first `guard` row is the gate. **An acceptance-PR that is done-but-unmerged typically shows exactly this shape at its head: the acceptance vertical green (guard·check-pr-acceptance success, #1644 ticked issue) and a SAME-PR `check-pr-base` red for base drift** (`HEAD` merge-base with `origin/main` = an older merge, foreign commit self) — that red is a rebase onto the current main tip, owned by the PR's lane (I never push to another's branch, #1706) and it is NOT a re-open of the acceptance verdict. Name the rebase target (current `origin/main`) and hold; re-post a branch verdict once a concluded run at the rebased head is all-green.
- **A peer can re-dispatch "the boxes are still unticked / post the unblock verdict" against a SUPERSEDED head after your seam tick already landed — verify your own write-back persisted before ever re-ticking, and never re-tick a completed verdict-gated tick.** Measured on #1797: I completed the #1644 seam tick at 15:15Z (`acceptance_writeback writeback --issue 1792 --proven 1..6 --verdict-ref 'reviewer=llgenie-pr-reviever comment=6661591003 head=b4bc5420 …'` PATCHED 6/6, each box carrying the `(proven: …)` marker); a later planner dispatch cited head `b4bc5420` and "6 violation(s)" as if current — but the wire head had advanced to `05724a17c` and the boxes were 6/6 `[x]`. The cited run 42052094718 was created 15:09Z at the old head, BEFORE the tick. Correct action: re-read the live PR head + the live issue's box marks + the run's created-at, confirm no work is owed (the verdict + tick are done), post a correction naming the comment id of the seam's produced tick, and explicitly say "no re-tick" (#1644 stays seam-sanctioned). Do NOT post a fresh verdict or a second write-back against an already-ticked issue. When a dispatch premise contradicts what you measured, trust the live wire (PR head sha, issue `edited_at`/`updated_at`, box mark of each `## Acceptance criteria` item, and the CI run's `created_at` vs your tick time) over the peer's textual claim — a threshold veto surfacing "6 violations" on a pre-tick run is the faithful hold, not evidence the fix failed.
- **The acceptance-hold release proof is the LIVE-BODY local re-read + the rendered-body class check — a CI rerun is optional evidence, not a requirement, and it must group by run id.** After any `--proven` tick, prove the drop with `scripts/check_pr_acceptance.py check --body-file <FRESHLY fetched PR body>` (must fall to `OK … rc 0` for a full tick, with zero `tick-unprovable` AND zero `acceptance-unchecked` on the rendered body — a held out-of-scope criterion is the only legal remaining row). If you additionally rerun a stale CI run for the durable CI-side record, enumerate EVERY stale run at the head first (`gh pr checks` + each row's `detailsUrl` → run id) and `gh run rerun --failed` once per distinct run id — a designed hold can red the guard AND a separate ci-scope workflow run, each with its own `check-pr-acceptance` job, so one rerun leaves the other red. The local live-body re-read is authoritative; the rerun just moves the evidence onto the CI wire. Full detail: `references/acceptance-hold-release.md` + `references/verdict-writeback-verification.md` §6.
- **A write-back on a RE-STAGED head cites the new sha, and the write-back itself creates NO CI run id.** When the rebase lane re-pushes a branch onto live main (`#1848`: `dd57b47e92` → re-staged `9fd08a43` on base `b4e366c2`), re-run the evidence battery (tests, `git merge-tree --write-tree <base> <head>`, the acceptance gate) at the NEW head and write `--verdict-ref` with the new sha — old-head citations on the issue thread are historical, not the tick's anchor. The write-back is an ISSUE-BODY PATCH (`PATCHED #<n>`), so "the write-back run id" a lane asks for is the gate evidence RUN at the head (e.g. run `42231931400` @ `9fd08a43`), never a run the PATCH creates. Full detail: `references/verdict-writeback-verification.md` §1.
- **A write-back ticks only the criteria the PR actually delivers — never the N/N a dispatch requests.** When a dispatch asks for a full tick to unblock a gate-PR, classify each linked-issue criterion against *this PR's diff*, tick only the delivered subset (`acceptance_writeback writeback --proven 2,4,6`, dry `--dry` then live), leave the rest `- [ ]`, and report that the gate reading them will correctly stay red until the other vehicles (a fleet rollout, a follow-up PR) land. Over-ticking fabricates proof no diff supports. The `check-pr-acceptance` out-of-scope exemption matches a criterion's **first three words** against the PR body's `## Not covered` — so "out of scope" in a dispatch is not the same as "exempted by the gate", and an undelivered-and-unrestated criterion still reds. Full detail: `references/verdict-and-completion-discipline.md`.
- **The last PR of a fleet-rollout closing the umbrella cannot be un-ticked by a pre-merge write-back when one criterion is SELF-REFERENTIAL — measure the ordering before promising an unblock, and state the release path as merge-first.** When several PRs each `closes #umbrella` and cumulatively deliver its criteria, a criterion phrased "the PRs merge → downstream #X becomes tickable → a verdict ticks it" depends on *this* PR's own merge: the write-back needs the downstream tick, which needs the merge, which the red gate is holding — a closed loop no pre-merge tick can break. Verify by reading the umbrella's criteria against each PR's diff (which are delivered NOW by already-merged siblings vs which require the merge itself), then report the honest release path: the last PR merges first (owner path — never this lane, #1088), THEN the verdict-gated write-back ticks the delivered subset, THEN the downstream item ticks and the grandparent reaches N/N. Present the acceptance-red at the head as the correct by-design umbrella-hold, not a defect, and name which criteria the merged siblings already prove (cite the merged contract's file:line in `main`, not the PR's). This is the ordering twin of "tick only the delivered subset" above: same rule, but the delivered subset cannot include a criterion whose proof *is* the merge.
- **A RUNTIME-VERIFICATION criterion — one whose only proof is a run that cannot exist until the PR's change is live — is a third class beside "delivered now" and "self-referential": hold it unticked pre-merge, and say the reason is structural, not deferral.** A criterion requiring "a push=true vllm/rocm engine-build cell (run id + job id) reports completed/success at the raised cap" (issue #1818 criterion 2) cannot be proven at the introducing PR's head because a push-triggered run at the NEW cap only happens once the workflow is on main — the PR itself does not fire that run. This is NOT the self-referential closed loop (#948), and NOT a "delivered subset" omission (#947): the diff delivers the *policy* (the matrix-aware cap), but the *verification* requires an on-wire cell that pre-merge structurally does not exist. Tick the policy criteria the PR proves (e.g. criterion 1 = the exact matrix-aware expression in the workflow, pinned by a unit test that evaluates the expression over the emitted matrix — rocm→360, others→240), tick the change-note/gate criterion (criterion 3), and hold the runtime cell criterion unticked with the reason stated on the verdict ("no completed push-trigger cell exists at this head today; current cell run X still in_progress at the OLD cap" — an in-flight cell is no verdict). State the release path: merge → the cap exercises on-wire → the criterion becomes provable + ticks. Do not fabricate the cell by citing an in-progress or old-cap run. Measured on #1820 (head 9aecbfab, run 42148365235, guard job 127665239152): verdict 6674989587 ticked #1818 criteria 1+3, criterion 2 honestly held, write-back read-back 2/3.
- **A dispatch claiming "the artifacts are sha-identical both sides" is a claim to reconcile against measurement, not to rubber-stamp — tree≠live is EXPECTED when the PR itself adds the block.** When a fold/versioning dispatch says "sha256 <id> both sides (live==tree)", measure both yourself (`sha256sum` of the tree file and the live profile file at the exact path, after `find … -path '*<skill>/SKILL.md'` to locate live — it is under `~/.hermes/profiles/<lane>/skills/`, not the tree). A fold that copies live→tree *then appends* a new contract block legitimately lands tree≠live (tree = live + the added block); that is the PR working, not a defect — say so explicitly ("substance confirmed, tree adds the block the dispatch's exact sha omits") rather than red-ing the PR on a stale number. Only treat a mismatch as a defect when the tree is *missing* content the live has (silent truncation) or the added block is not verbatim. This is the fold-specific instance of "trust the live wire over the peer's textual claim."

### The two tree-side checks (`--soul-rules`, `--soul-shrink`)

When the ask is "can this `agents/` tree land?", one gate is not enough — the repo's
`check_agent_profiles.py` sees only shrinkage, and it is blind to a rule stated twice:

```bash
python3 scripts/pr_watch.py --soul-rules  <ref>   # per lane: r13/r14/r15 → ok | ABSENT | DUPLICATED
python3 scripts/pr_watch.py --soul-shrink <ref>   # per file: tree bytes vs live → LIVE-LONGER | LIVE-MISSING | ok
```

`--soul-rules` exists because a rule a lane does not state is a rule it cannot apply, and a rule
stated twice is two texts that drift (measured: `remedy.**` versus `remedy**` in the same file,
#922's family). `--soul-shrink` reproduces the gate's byte comparison from `git show` + the live
profile, so the two results can be cross-checked instead of trusted — run both back to back and
compare their finding sets. Report them as two verdicts — `ABSENT`/`DUPLICATED` for statements,
`LIVE-LONGER` for bytes — never as one "tree is wrong". `live=absent` is deliberately distinct from
`live=0`: a missing profile and a shrinking one are different fixes.

**This gate's result is `(PR head, live profiles at run time)` — it can go red under a PR nobody
touched.** The comparison reads files on the machine, so a peer lane editing its own live `SKILL.md`
mid-hour adds a finding to a tree whose head has not moved; a count taken ten minutes ago is a
sample, not a verdict. State the clock and the finding count together ("6 findings, 09:24Z"), re-run
immediately before reporting the tree as ready, and re-run again after the repair push — five findings
becoming six with the PR unmoved is the expected shape, not a contradiction. Do not carry an earlier
green forward as current, and do not tell a lane its gate "passes" without the time it passed.
