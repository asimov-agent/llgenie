---
name: llgenie-bot-orchestration
description: Use when an llgenie bot is idle and issues are waiting.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llgenie, orchestration, bots, delegation, gh]
---

# llgenie bot orchestration: idle bot → waiting issue

## When to Use

Not a code task. Use it on every llgenie pass, and whenever the owner asks "what are the bots doing?": a bot is
idle (no run in its cron slot, or runs all `skipped`), a claim looks live but no branch exists, or a branch carries
work with no PR. It ends in a dispatch with evidence, never in an implementation.

The planner never implements. This is the loop that keeps the fleet working: measure quiescence, measure the
backlog, dispatch, report the evidence.

**Idleness is the defect.** Every pass ends in a dispatch, a close with evidence, or a written reason nothing could
move — never in "waiting". A recurring tick (a cron job running this skill, every 30–45 min) is the mechanism that
makes the rule true rather than aspirational; when it fires, run the whole pass and report what changed. A stalled PR
is the same failure as an idle bot: a conflicted PR gets no CI run at all, so nobody will fix it unless you dispatch
the rebase bot or the host implementer.

## 0. Preflight: bring the tree to upstream main and re-read AGENTS.md

Every pass, before measuring anything, and every dispatch, before an implementer starts:

```bash
git -C /home/asimov/repository/git/llgenie fetch origin main
git -C /home/asimov/repository/git/llgenie rev-list --left-right --count HEAD...origin/main   # expect: 0 0
git -C /home/asimov/repository/git/llgenie log --oneline -1 origin/main                       # the sha to cite
```

Then re-read `AGENTS.md` at that sha — 87 KB, 1,302 lines, and it changes weekly, so a memory of it is not a reading.
The dispatch brief names the sha (`main@<short>`); the implementer opens its worktree off `origin/main` and reads
`AGENTS.md` there before its first edit. A `HEAD...origin/main` count that is not `0 0` on a clean checkout is a
finding: fetch, fast-forward, and say which paths moved. Issue #792 makes this a gate (`make bot-preflight`, an
`AGENTS: <sha> <bytes>b <lines>l` line required in the PR body by `check-pr-hygiene`).

## 1. Measure quiescence per workflow

Cron slots live in `docs/BOTS.md` and in each workflow's `schedule:`. Compare the newest run to the slot:

```bash
for wf in issue-bot issue-refiner fix-bot security-bot registry-sync run-failure-reactor engine-bump auto-merge; do
  echo "== $wf"
  gh run list --repo asimov-agent/llgenie --workflow $wf.yml --limit 3 \
    --json databaseId,createdAt,conclusion,event,headBranch \
    --jq '.[]|"\(.createdAt) \(.conclusion) \(.event)"'
done
```

A bot is idle when it has no run inside its slot, or when its recent runs are all `skipped`.

**A missing slot is not proof of a broken bot — GitHub delays and drops scheduled runs.** Measured: an hourly workflow
(`43 * * * *`) produced runs at `13:29`, `06:18`, `00:42`, `21:27`, `16:50` — gaps of 6–7 hours, and none of them on
`:43`. So neither the cron string nor the timestamp of the last run can assert what ran, and "the 14:43 slot never
fired" is a fact about the scheduler, not about the lane. Confirm a genuinely idle bot with
`gh run list --workflow <f> --limit 20` against an **expected-slot count** over the same window, and when you report a
missing slot, say which of the two you measured. (The same discipline as `cancelled ≠ failed`: the instrument, not the
number.)

**`skipped` is the signal that matters**: `issue-bot` skips the implement leg on a `refine`/`close` verdict, so a green run can mean
the bot did nothing. Check the step, not the workflow conclusion:

```bash
gh run view <id> --repo asimov-agent/llgenie --json jobs \
  --jq '.jobs[]|.name as $j|.steps[]|"\($j) :: \(.name) \(.conclusion)"'
```

## 2. Measure the backlog

```bash
gh issue list --repo asimov-agent/llgenie --state open --limit 200 \
  --json number,title,labels,comments,updatedAt --jq '.'
gh pr list --repo asimov-agent/llgenie --state open --limit 100 \
  --json number,headRefName,mergeStateStatus,title --jq '.'
gh api repos/asimov-agent/llgenie/branches --paginate --jq '.[].name' | grep '^agent/'
```

Three backlog classes, each with its own owner:

| class | tell | owner |
|---|---|---|
| actionable | `agent:implement`, no claim, no branch | CI `issue-bot`, or the host implementer |
| phantom claim | `bot-claim:` TTL live but no branch and no PR | host implementer (release the claim in a comment first) |
| orphan branch | `agent/issue-<n>-*` with no PR (issue open or closed) | re-dispatch if the issue is open and the branch is fresh; delete if the issue is closed or the branch is far behind |

Verify the phantom claim, never trust the claim text: `gh api repos/asimov-agent/llgenie/branches/<branch>` — a
404 with a `changed=true, PR: none opened` comment is the CI implement leg dying before push (tracker #770's class).

## 2b. Route to the bot that owns the work class

The fleet is not one implementer. Listing the roster from memory loses an hour: a rebase sent to the general
implementer sits behind six unrelated items while the bot that exists for conflicted PRs is idle. **Read the roster
before every dispatch** (the `message_agent` error lists it exhaustively; a rejected name is a cheap way to refresh
it) and match the work class, not the queue length:

| work class | owner |
|---|---|
| conflicted / `DIRTY` PR, rebase, force-with-lease | `llgenie-pr-merge-conflict` |
| issue implementation, one branch + one PR | `llgenie-issse-implementer` (triple-s typo is real) |
| architecture pass, decomposition, new issue batches | `llgenie-architect` |
| workflow / CI pipeline edits | `llgenie-ci-pipelines-maintainer` |
| docs, README, ARCHITECTURE prose | `llgenie-documentation-maintainer` |
| engine pins, image builds, serving flags | `llgenie-engine-improver` |
| security scans, advisories, floors | `llgenie-security` |
| PR review, request-changes | `llgenie-pr-reviever` |
| quarantine/claim bookkeeping, issue bodies, dispatch | the planner (you) — never code |

When a specialist owns the class, dispatch there even if the general implementer is the documented fallback: a
specialist's brief is shorter, it already carries the repo's constraints, and it does not serialise behind unrelated
work.

## 3. Dispatch

- **In-repo CI bot**: ensure the label, and post a comment naming the scope and the acceptance criteria. Do not
dispatch while a `bot-claim:` TTL is live.
- **When `message_agent` returns `queue_full`, the DM never landed** — a busy lane's inbox refuses admission and the
  receipt says "retained", not delivered. Do not resend (that adds to the same queue). Put the decision where it
  cannot bounce — a comment on the PR or issue, naming the exact command and the unblock — and tell the lane in the
  next message that lands that the instruction lives there. A lane can sit idle for an hour "waiting for a call"
  that is only in a queue: the artifact is the comment, not the delivery.
- **A task on an existing PR branch must use `--workspace dir:<the worktree that already holds it>`.** `--workspace
  worktree --branch <existing>` fails twice with `'<branch>' is already used by worktree at <path>` and auto-blocks the
  task on `spawn_failed`; the `worktree:<path>` variant silently **ignores the path** and cuts a fresh `wt/<task>`
  branch off main — a second vehicle for an issue that already has one. Verify with
  `git -C .worktrees/<task> rev-parse --abbrev-ref HEAD` immediately after dispatch, not after the lane reports.
- **There is a global worker cap (5 observed).** `Spawned: 0` with a task left `ready` is a capacity answer, not a
  failure: `hermes kanban stats` shows the running count and the per-assignee split. Report the queued task and its
  unblock condition ("spawns when one of the five finishes") rather than re-dispatching.
- **A delivery is landed when the task's worktree shows edits**, `git -C <worktree> status --porcelain`, not when the
  task reads `running`.

- **When `message_agent` is not in the toolset (every cron pass), the host-bot channel is the kanban board**:
  `hermes kanban boards set-default-workdir default <repo>` once (a `worktree` task without it auto-blocks after
  two `spawn_failed`), then `hermes kanban create "<title>" --body-file <brief> --assignee <profile>
  --workspace worktree --branch <branch> --created-by llgenie-planner --idempotency-key llgenie-issue-<n>`,
  `--parent <task>` to gate a dependent issue, and `hermes kanban dispatch --max 5`. A delivery is landing only
  when the task reads `running` *and* its worktree shows edits: `git -C <repo>/.worktrees/<task> status --porcelain`.
  `kanban runs <task>` tails the *first* attempt, so a stale `spawn_failed` diagnostic sits above a healthy run.
- **Every dispatch starts with the preflight**: the `main` sha you measured, plus "open a fresh worktree off
  `origin/main` and re-read `AGENTS.md` there before the first edit". A brief with no sha is a brief the implementer
  cannot check itself against.
- **A full inbox on the natural owner is not a reason to wait.** When the specialist for the class is refusing deliveries (`queue_full`) for hours, dispatch the same brief to the nearest specialist **with capacity** — a CI-lane task to the maintainer rather than the general implementer — put the full trail on the issue so the artifact survives, and say in the message that the issue wins if it and the DM disagree. The owner's expectation is that work moves: a queued name is not an assignment.
- **Host implementer** (`llgenie-issse-implementer`, triple-s typo): `message_agent` with the issue number, the
  verdict, the measured state, the required direction, the constraints (fresh worktree off `origin/main`, one
  ready-for-review PR, `closes #<n>`, gates through make, never merge) and what to report back. It has no cron — it
  only works when messaged. Queue several items in one message only if you say which goes first.

## 3b. Accepting issues another agent filed

A capable bot can hand you a batch of issues with a suggested order and a one-line rationale each. Take the order as
advice, never as measured fact:

- **Prove the baseline sha is really `main`.** `gh api repos/<o>/<r>/commits/main --jq '.sha'`, then
  `git branch -r --contains <sha>`. A sha whose only home is `fork/<branch>` is an unmerged PR branch, and every
  number in that batch then describes code nobody can review yet.
- **Re-measure the counts on `origin/main` without creating a worktree** — creating one to check is debris you are
  forbidden to clean up: `git grep -l '<pattern>' origin/main -- <path>`, `git show origin/main:<file> | wc -l`,
  `git grep -c '<def name>' origin/main -- scripts`. An acceptance criterion quoting a wrong count cannot be ticked
  honestly by a reviewer, so the count is part of the contract.
- **Correct in public.** Post the measured table as a comment on each issue whose numbers moved, and tell the filer to
  re-measure and comment with the sha it read. Then dispatch, quoting the sha the implementer must cite.
- **Order by capacity, not by dependency alone.** Dependency says what *can* start; the queue says what *should*.
  Independent items are held rather than queued ahead of work already in flight.

## 3c. A starved runner queue is a finding, not a reason to push harder

Before dispatching, count `gh run list --repo <o>/<r> --limit 40 --json status` by `queued` versus `in_progress`.
Many queued with none running means the platform is not scheduling: every extra `workflow_dispatch` lengthens the
queue without starting anything. Do the blocking fix through the host implementer instead (a rebase, a one-line
guard) and hold further CI dispatches until it drains. “Queued” is never “red” — say so in the brief, or an
implementer will chase a phantom failure.

**Distinguish a stuck queue from a churning one by the age of the oldest queued run.** Queue length alone says nothing:
43 queued with the oldest created minutes ago is a backlog being consumed while new runs arrive (one runner against
many PRs, every push adding one); 43 queued with the oldest hours old is a queue nothing is draining. Read the count
beside `gh api '.../runs?status=queued&per_page=3' --jq '.workflow_runs[0].created_at'` and beside `status=in_progress`,
then diagnose: churn is fixed by fewer triggers per PR (sha-keyed `concurrency`), a stuck queue by finding the runs
holding the runners — often matrices for **already-merged** PRs, whose verdicts nobody will read.

**A job queued on a label no runner matches never concludes — and that reads as "blocked on review".** Count queue length and you will blame pressure; read the job's `runs-on` and you find the real cause. The repo ships the instrument (`scripts/queued_run_alarm.py`), and its output names the mechanism: every stalled job carries the same label, GitHub does not fail a job whose label matches nothing, so the run never concludes and every PR's checks stay pending.

```bash
python3 scripts/queued_run_alarm.py --repo <o>/<r> --minutes 30   # prints label + age per stuck job
gh api repos/<o>/<r>/actions/runs?status=queued --jq '.workflow_runs[]|"\(.id) \(.head_sha[0:8]) \(.created_at)"'
```

Two consequences. **A PR whose every remaining job is that label is complete, not unfinished** — say "supply-limited, 0 failures" rather than "waiting on review", or the owner reads a verdict problem into a capacity problem. And **prove the cause before proposing the fix**: change ONE row to a neighbouring label on a scratch branch and record whether the job picks up (picks up ⇒ the label is not provisionable on this account's plan; still queues ⇒ capacity/billing, which is the owner's to fix and no workflow edit will clear). **Carry a control leg in the same probe run** — a cheap `ubuntu-latest` job beside the suspect labels. Without it, "all suspect labels queued" cannot distinguish a broken workflow from starved labels; with it, a control that finishes in seconds while the suspects queue for minutes settles the question in one run, and a probe whose suspect leg merely queues for "about the normal lag" proves nothing either way. Delete the probe afterwards: it is evidence, not a PR. Run this in a *separate* lane from the queue-clearing: cancelling runs and pausing schedules cannot conjure a runner, which is why a sweep earlier in the evening frees nothing.

**Two matrices competing for one runner pool is one matrix.** Before letting a lane open a new PR (or push a fresh
branch) while another verdict run is live, count what is already running: a 27-job matrix queued behind a 25-job matrix
means the second verdict arrives after the first, and the first is the one the board is waiting on. Hold the new PR,
say the release condition out loud ("open it the moment <run id> concludes, green or red"), and prefer making that
condition self-executing — a watcher on the run id — over a promise to remember. The same arithmetic applies to
dispatching probes: a probe that cannot answer its question until another change merges should wait, not compete.

How to read what CI is actually saying — check-run conclusions, `mergeStateStatus` versus "all checks green",
queue-age diagnosis, and how to run a cancel campaign without killing the runs you meant to keep — is in
`references/ci-state-and-queue.md`. Three rules from it are always-on:

- **`gh pr checks`'s "fail" column is not a failure count.** Only `check-runs` conclusions are: `success`, `failure`,
  `cancelled`. `cancelled` means *not yet* — a newer run superseded it (`cancel-in-progress` on PRs), so the PR has no
  verdict and needs one fresh completed run. Use `gh pr view <n> --json statusCheckRollup` and count the conclusions.
- **"All checks green" is not "mergeable".** Auto-merge gates on `mergeStateStatus == CLEAN`, not on check names;
  `BLOCKED` + `REVIEW_REQUIRED` means the checks passed and a human approval is outstanding — a different sentence for
  the owner than "not ready".
- **`BLOCKED` cannot tell you whether a check was enforcing.** Where `REVIEW_REQUIRED` is on for every PR, that state
  masks `UNSTABLE`, so a PR with a failing check and one with none read identically (`BLOCKED` both). A probe that
  plants a failure and observes `BLOCKED` therefore proves nothing about checks. **`UNSTABLE` is just as blind in the
  other direction:** a PR with eight checks still running and **zero failures** reads `UNSTABLE`, so the value
  cannot distinguish "a non-required check failed" from "checks have not finished" either. Four states, three of them
  collapsing to "not mergeable": failed check → `UNSTABLE`; still running → `UNSTABLE`; review required → `BLOCKED`;
  green + approved → `CLEAN`. Record `reviewDecision` and `isDraft`
  **beside** `mergeStateStatus`, take a before/after pair on the same PR, and treat "advisory vs blocking" as
  answerable only by the merge decision (`auto_merge.decide()` refusing on `!= CLEAN`), not by the badge.
- **Check whether the repo has required status checks before designing a gate contract.**
  `gh api repos/<o>/<r>/branches/main/protection` (404 = none) and `gh api repos/<o>/<r>/rulesets/<id> --jq '[.rules[].type]'`.
  A "skipped class deadlocks branch protection" premise is wrong on a repo with no required checks; the surviving risk
  is legibility — a skipped stage nobody can see afterwards — and the fix is an always-running scope report, not a
  required-check redesign.

## 3d. Two PRs, one seam: prove the merge before you pick an order

When two open PRs touch the same line — both adding a row to the same gate list, both editing the same README
paragraph — an order recommendation without a proven merge is a guess. Prove it read-only, no worktree debris:

```bash
git -C <repo> fetch origin \
  'refs/pull/<a>/head:refs/remotes/origin/pr-a' \
  'refs/pull/<b>/head:refs/remotes/origin/pr-b' --force
git -C <repo> merge-tree --write-tree origin/pr-a origin/pr-b     # tree sha + one line per conflicted path
```

Then ask the PR's author for the gate output on the *merged* tree (skill check, tests, docs, wiring) and post the
resolution recipe as a comment on **both** PRs — the owner may land either one first, so the recipe has to be where
the decision happens, not in a DM. Recipe shape: union the two data lines, keep both test cases, and rewrite any
prose that asserted singularity.

**The trap is prose, not code.** A naive "keep both" on a shared README leaves two paragraphs describing the same
thing and a sentence that becomes false the moment there are two instances ("X is the one host skill"). Read the
merged text for sentences whose subject count just changed, not only for conflict markers.

Recommend the order on bookkeeping grounds — mechanism before second instance — and say plainly that either order
works once the recipe exists. The merge itself belongs to the owner.

## 4. Report with evidence

A `delivery_id` is not a task landing. Re-check the repo for the branch, the PR or the comment that proves the bot
started; if a delivery comes back `pending or unknown`, measure once more before re-dispatching, and say plainly that
the pickup is unconfirmed. `pending or unknown` is the routine receipt for a delivery that is still in flight — never
read it as failure, and never resend on it alone.

## 4b. Tell a slow bot from a looping one, then break the loop

How to measure a busy-but-idle bot, the exact-commands brief that breaks a loop, and the queue-withdrawal rule are in
`references/fleet-failure-modes.md`. The short version: measure its own profile, not the repo —

```bash
stat -c '%y' ~/.hermes/profiles/<profile>/state.db                 # last write = last activity
tail -5 ~/.hermes/profiles/<profile>/logs/agent.log               # "API call #N" = how many turns burned
git -C <its worktree> log --oneline -1; git -C <its worktree> status --porcelain | wc -l
```

A live session with a high turn count, an unchanged branch tip and a fixed set of uncommitted paths is a loop, not
progress. Breaking it is a dispatch problem, not a persuasion problem: cut the brief to the exact commands, remove the
unreachable gate, withdraw the rest of the queue in writing, and say which items are *parked, not deferred*. Pushing a
third or fourth polite brief at a looping bot is the mistake — the artifact count has not changed and the queue grows
while you rephrase. Full recipe in `references/fleet-failure-modes.md`.

## Your own rules are a repo artifact

A host agent's `SOUL.md` and skills live outside version control by default, so an instruction change is the one
behaviour change nobody reviews — and the host agents hold the write credentials. Any change to this skill or to the
planner's `SOUL.md` goes through an llgenie issue and a PR that commits the text under `agents/<profile>/` (issue
#791 is the tracking issue and the layout). File the issue first, dispatch the PR, then sync the profile from the
repository; never edit the live `SOUL.md` and stop there.

**A rule learned by one lane must reach every lane, and verbatim.** When a session produces rules the whole fleet
needs (destructive-action prohibitions, reporting shape, freeze semantics), file **one** issue carrying the rules as a
single canonical block, then send every active profile the same instruction: copy the block *verbatim* under one
heading, and add **one lane-specific rule the canonical text cannot express** (the reviewer's "retract in the PR, not
in a DM"; the rebase lane's "one push per PR then freeze"; the CI lane's "authorised is not now"). Verbatim matters
because the profiles are then diffable against each other — paraphrases drift within a week and each lane ends up
with a subtly different fleet.

**Prove the copy, do not assert it.** Each profile PR should show `block in soul` computed from the issue body (extract the block, test membership) rather than "copied verbatim", and the profile gate should be run with a **negative control** — delete one canonical rule and watch the gate red with a message naming the missing rule, restore, re-run green. A profile SOUL is a protected agent-instruction file: an approval prompt that times out is escalated in one line naming the file and the reason, never worked around with a heredoc or `cp`.

**The canonical block grows after the copies are opened, so re-diff at merge time.** Rules are added while profile PRs are already in review, which silently makes every earlier copy stale: the issue body is the source of truth and the PR is a snapshot of it. Before approving or merging any copy, diff the artefact against the current body — extract the block, assert membership, and compare byte counts and bullet counts (`<n> bytes · <n> bullets`). A copy showing 1758 bytes / 10 bullets against a 2137-byte / 11-bullet body is *not* "verified in #<issue>", it is one rule behind, and merging it ships a SOUL missing the rule that lane earned. Hold the merge, put the hold as a comment on the PR so the owner sees it, and let the lane push the missing bullet once its current run concludes — the amendment is one line and needs no re-review. Applied to every copy: a "verified" status is a comparison against the source as it stands now, never a claim made when the file was written.

**Base the profile PRs on whichever branch actually introduces `agents/`.** When that directory is not yet on the default branch, a profile PR based on `main` carries the whole introducing diff and cannot be reviewed on its own; base it on the branch that creates the tree, fetch it via `refs/pull/<n>/head` when the branch ref is not published, and say in the body that the diff collapses once the parent lands. Use `Refs #<issue>`, not `closes` — one of N profiles does not close a fleet-wide issue.

**Decide *which* skills to version mechanically, not by reading them.** Asking "which of these sixty are
behaviour-bearing?" invites either a 60-file PR nobody reviewed or an omission. Encode the answer instead: a profile
file is in scope when it is **not byte-identical to the bundled copy**, recorded as a generated manifest (`path ·
sha256 · authored|vendored`), with the profile gate failing when an *authored* hash no longer matches the tree or when
a profile carries a skill absent from the manifest. That collapses the review to the authored diff, and it turns the
next unversioned host edit into a gate failure rather than a confession — which is the whole point of the issue: hosts
edit their own skills silently and self-report afterwards.

Two practical notes. **The issue is the channel, not the DM:** half the fleet's inboxes refuse admission
(`queue_full`), so the issue body carries the block and the DM only says "read it, then PR". And **each rule earns its
line from a measured cost** — write the cost as the reason in the issue table, because a rule with no mechanism behind
it is the first thing a future lane deletes as bureaucracy.

## Never prune: report worktrees instead

`make worktree-prune`, `git worktree prune` and `git worktree remove` are **owner-only** — **including a lane's own
worktrees.** "They were mine" is not an exemption: the lane cannot know what a delete takes either. Two of the most
dangerous trees look exactly like housekeeping — one that needed `sudo` (root-owned artifacts, so the delete half-ran
and left debris) and one whose PR is **closed** ("PR closed" is not "tree empty"; that is where uncommitted repair
work lives). Say which paths are stale and stop there. The prune deletes
directories, and its "already merged" test reads the branch REF, so a worktree with uncommitted work looks stale — a
bot that prunes destroys the run it is standing in, and root-owned debris makes it exit non-zero having deleted what
it could reach and left the rest. Only the owner can read what a delete will take.

Measure, then report, then leave it:

```bash
git -C /home/asimov/repository/git/llgenie worktree list --porcelain
git -C /home/asimov/repository/git/llgenie merge-base --is-ancestor <tip> origin/main; echo $?
gh pr list --repo asimov-agent/llgenie --state open --json headRefName
```

A stale worktree is a finding for the owner (`make worktree-report`, issue #794), never a cleanup you run. Say which
paths are stale; do not delete them, and do not tell an implementer to.

## Verify the population, never the number

A count can be true and still validate nothing. Measured case: an issue claimed "11 wrappers", the check
`git grep -c '^\s*def (_run|_sh)('` returned 11, and it was ticked ✓ — but the 11 that mattered was a **third**
population (the wrappers whose bodies never read `.returncode`), and the true population of wrappers was 30. Three
sets, two of them coincidentally the same size.

So when checking a filed number: name the population first (`defs named X` vs `defs whose body lacks Y`), state the
command that enumerates it, and check membership of two or three known members by eye. A ✓ attached to the wrong
denominator is worse than no check, because it licenses a dispatch that under-scopes by two thirds.

Command-level recipes for the checks above (baseline sha, conflict proof, approval provenance) live in
`references/proving-bot-claims.md`.

## The sha comes from this turn's read, never from your last message

A head read three messages ago is a claim about a branch that has moved. Carrying it forward is the most expensive kind of error here because it is invisible: the number looks measured, the lane answers about a different commit, and an hour goes into reconciling two true statements about two heads.

So **every message that names a sha or a count re-reads it in the same turn** — `gh pr view <n> --json headRefOid,mergeStateStatus` — and when you quote a lane's finding, attach the sha it was measured at. Two rules fall out:

- **A verdict, a finding or an "urgent" label is only valid at its head.** "`check-dispatch-forms` is red" and "the exit code is 2" were both true at a superseded sha and false at the live one; before pressing urgency, re-run the command at the head you are about to name. When a lane says your finding is stale, believe the measurement, not your memory of it.
- **A sha that appears nowhere is worse than no sha.** `gh api repos/<o>/<r>/commits/<sha>` returning a 404, or a `git branch -r --contains` returning empty, means the id came from a closed PR or an abandoned branch — say so and stop quoting it, rather than letting the next reader chase a tree that cannot merge.

## Cite the invariant, not a single number

Two agents can measure the same artifact and report different numbers without either being wrong: bytes vs characters
(8 em dashes = +16 bytes over `len()`), `merge-tree A B` vs `B A` (different commit id, same conflicts), a branch ref vs
a worktree tip, `gh issue list` default page size. Say the invariant — "byte-identical, 55 lines", "three conflicted
files", "same tree sha" — and put the raw number beside the method that produced it, or the next reader spends a turn
on a reconciliation that changes nothing.

## Timestamps are UTC; your clock is not

`gh` returns `...Z` timestamps and `date` prints local time (CET = UTC+1 here), so a filter like
`createdAt > "2026-10-28T15:50"` hides everything filed in the last hour: it compares a local wall-clock string against
UTC, and an issue filed at `14:49:12Z` reads as eleven hours early. Use `date -u` for the cutoff, or compare with
`--json createdAt` values directly, and before declaring something missing check whether the filter, not the
deliverable, is what excluded it.

**An age is a subtraction, not an impression.** "Queued for ninety minutes" gets repeated as a fact and is nearly
always a stale reading of a run that has since been superseded. Print both operands from one shell in one turn:

```bash
date -u +%H:%MZ
time gh api repos/<o>/<r>/actions/runs/<id> --jq '"\(.status) created=\(.created_at) updated=\(.updated_at)"'
```

A claim like "queued 100 minutes" that arithmetic turns into 7 discredits every other number in the report, including
the ones that were right. Ask the reporter for `now` and `created_at` side by side rather than arguing the estimate.

## Draft PRs are forbidden — real PRs only

Every dispatch says: open the PR **ready for review**, never as a draft, and flip any draft with `gh pr ready` before reporting it. A draft is invisible to auto-merge, to the merge queue and to a reviewer scanning for work, so a draft reads as "no PR" on the board while the work exists. Before declaring a lane blocked on approvals, measure `gh pr list --json isDraft` — three drafts (#846, #838, #780) sat while the board was reported as stuck on review.

## Auto-merge is permanent policy, never part of a pause

When the owner pauses automation, **leave `auto-merge` enabled**. A disabled auto-merge looks identical to a deleted one — no workflow reds, PRs simply accumulate — and a night of green PRs will not land while it is off. Owner instruction: green PRs are auto-merged, and that behaviour must never be removed from CI. If a pause is required, list explicitly which workflows stay on (auto-merge at minimum) and restore the rest from that list, never from memory. Guard it with a test that fails if `auto-merge.yml` is deleted, disabled, or loses its automatic trigger.

**Separate "the merge job never ran" from "it ran and deferred".** `completed / success` on a merge sweep means it
decided *not* to merge — a green conclusion is not a merge — but a `queued` sweep means it never executed, and with a
small runner pool that is the common case: three consecutive sweeps sat queued while the PRs they were meant to merge
still read `BLOCKED / REVIEW_REQUIRED`. So before diagnosing the decision logic, check the sweep runs themselves
(`gh run list --workflow auto-merge --json status,conclusion`), then read the sweep's own per-PR state line for the
condition it gated on. A `reviewDecision` that is empty rather than `REVIEW_REQUIRED` at decision time is a two-line
condition fix; a workflow that was still queued is not a bug at all.

Worktree/push hygiene: `references/worktree-and-push-hygiene.md`. Red CI runs: `references/ci-failure-attribution.md`.
Reading a failing job's log, `run.status` lying, queued-vs-running verdicts: `references/ci-state-and-queue.md`.
Gates that fire, shape changes, subset assertions, sync direction: `references/assertions-and-gates.md`.
Two PRs for one issue — pick by stack, close with a comparison: `references/vehicle-selection.md`.

## Never cancel a live matrix to "clear the queue"

A job that never starts and a job cancelled 21 minutes into running look identical from `queued_run_alarm` (it lists the *queued* rows; the cancelled ones are gone from that view). Read the **cancelled rows' start times** before believing either story — a row with `started_at` set and tens of minutes between start and cancellation was running, not starved:

```bash
gh run view <id> --repo <o>/<r> --json jobs \
  --jq '.jobs[]|select(.conclusion=="cancelled")|"\(.name) started=\(.started_at // "never") completed=\(.completed_at)"'
```

A label that matches no runner cannot produce a `success`, so one green job on that label in under a minute settles the hypothesis against "starvation" and in favour of "something cancelled it". Cancelling runs to free runners therefore destroys exactly the evidence you were waiting for — an installed macOS job proved the label provisions in 45 s on a run I had cancelled. Freeing a queue is not a fix; letting one long matrix finish is. No cancellation sweep without the owner's explicit word.

**The exception that is not a sweep: runs whose PR is already merged or closed.** When a small pool issues nothing,
read *which* runs hold it before blaming pressure — repeatedly the holders are matrices for PRs that landed or were
closed hours earlier, whose verdicts nobody will ever read (one such run held a platform row for 56–80 minutes while
41 runs queued behind it). Cancelling those destroys nothing and returns the pool; cancelling a live PR's verdict run
destroys everything. Decide per run with `gh pr view <n> --json state,mergedAt`: merged/closed ⇒ free the runner, open
⇒ leave it alone. A platform stage that no longer exists on the default branch is the usual reason an old branch is
still running it at all, so this is a queue of leftovers, not a queue of work.

**Do not generalise from one running specimen either.** Classify every stuck job by whether it ever had a runner before you describe the pattern:

```bash
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '.jobs[]|"\(.name) \(.conclusion // .status) runner=\(.runner_name // "NONE") started=\(.started_at // "never")"'
```

Measured across 70 runs on one repo: **65 rows `cancelled` with `runner_name` empty, 2 `cancelled` with a runner, 44 `queued` with none, 11 `success` with one.** So the pattern was *never issued a runner*, and the two that started were the exception — quoting those two as "they start and then get killed" inverts the diagnosis and makes removal look like a mitigation instead of the fix. The runner name is the field that separates the two stories; the conclusion alone cannot.

**Cancelling only frees the pool the run actually holds.** "Cancel the run whose verdict can wait" is wrong when the run you would kill is holding a **different** lane's resource: a PR holding a Linux runner while six macOS rows queue behind it frees nothing for a matrix waiting on macOS, and costs every success already paid for. Check which job is *running* (with `runner_name` set) versus merely *queued*, and cancel only when the run holds the pool the blocked matrix needs. And the deeper point: **cancelling frees a runner, only a timeout stops a runner being held** — if rows are stuck mid-step for tens of minutes, queue surgery cannot fix it and the missing `timeout-minutes` is the defect to file.

## Preflight must name the remote, not just the branch

The repo has been re-laid-out: `origin` can be the fork (`andyholst/llgenie`) while the real repo is `upstream` (`asimov-agent/llgenie`). `git fetch origin main` + `rev-list HEAD...origin/main` then validates the wrong repository and passes while upstream moved. There are **two main clones** and they name remotes differently: `/home/asimov/repository/git/llgenie` (`origin` = `asimov-agent`, `fork` = `andyholst`) and `/home/asimov/repository/git/ai-repositories/llgenie` (`origin` = `andyholst`, `upstream` = `asimov-agent`). Worktrees inherit the clone that created them, so `git fetch origin main` validates the fork in one tree and upstream in the other. Check `cat .git | head -1`, then `git remote -v`, then `git ls-remote <remote> <branch>` before any fetch or push, and resolve which remote URL is `asimov-agent` — never assume `origin` means upstream, and quote the sha you read from that remote. A `git fetch upstream` that dies with "upstream does not appear to be a git repository" is this, not a credential problem: the other clone calls it `origin`.

## A licence covers what to push, never when

A granted permission to change a branch is not permission to push it *now*. `concurrency: <workflow>-${{ github.ref }}` with `cancel-in-progress: true` means a push while a run at that head is in progress **destroys that run's verdict** — including a matrix 19 jobs deep with zero failures. The trigger for a push is *the current run at the head concluding*, never the licence arriving. Same paragraph as "rerun, never re-push": one push, then frozen until a run finishes.

Corollary for dispatch wording: name the head sha and say "do not push while a run at this head is in progress" — an implementer reading "authorised" alone will reasonably push immediately.

**The rule does not enforce itself, and a stall is the exact pressure that breaks it.** The combination that defeats it is predictable: an explicit instruction, a run frozen at a `updated_at` timestamp for twenty minutes, and a queue that makes finishing look expensive. Whoever holds the rule must **accept the wait** when someone with authority says "do it now" — that is a decision, not a reflex, and the planner's side of it is a standing preference stated in writing: **a body-, doc- or SOUL-only change never justifies cancelling a run**; it can wait for the conclusion. A rule about not destroying matrices must not be delivered by destroying one, and a lane that pushes anyway will report it honestly — record the cost and the standing preference, never a flattering version of the story.

## A merge is a dispatch trigger

After any merge to `main`, dispatch `llgenie-pr-merge-conflict` with the new `main` sha and the named trigger PR. The sweep is: measure staleness first (`gh pr view --json baseRefName,mergeable` per PR, `git merge-base --is-ancestor <tip> origin/main`) and report the list **before** rebasing; rebase in dependency order; resolve union-additions as unions and name every conflicted file with its resolution; one push per PR then freeze until that PR's run concludes (`cancel-in-progress` kills the verdict otherwise); never prune a worktree.

**The union rule has a drop case, and using it there creates debris.** "Keep both" is for two lanes' *additions*. When one side of the conflict is a commit being **dropped**, unioning keeps its remains: a change-record row dating a change to a PR that will never land, and a `.PHONY` key whose recipe no longer exists in the tree (`make <target>` then fails at runtime and no gate notices — a wiring check that only validates *called → exists* leaves *declared → exists* unchecked). Resolution for a drop is: keep the surviving side's row/key, delete the dropped side's, and say in the report which of the two you did and why. A sweep that finds nothing stale reports "no stale PRs, measured at <sha>" — that is a valid result. Dispatch it on the merge, not on a remembered intention: the owner's instruction is that the rebase bot is informed *when the PR has been merged*.

**`mergeable` is a snapshot too, and stale conflict state costs a force-push.** `CONFLICTING` is recomputed by the platform and can clear on its own; dispatching a rebase for a conflict you measured minutes ago hands the lane a licence to rewrite a branch that is already `MERGEABLE`. Re-read `gh pr view <n> --json state,mergeable,baseRefName` in the same turn as the dispatch, and give the lane one hard constraint: **never force-push to make a conflict disappear** — a resolved state is a reason to stop, not a reason to rewrite.

**Verify a swept branch's commit list before believing it.** A rebase or force-push that "resolved" a conflict can inject another branch's content as a fresh commit, reintroducing the duplicate the sweep was meant to remove:

```bash
git -C <repo> log --oneline origin/main..origin/<branch>     # every commit should be the branch's own work
git -C <repo> merge-base --is-ancestor <old-head> origin/<branch>; echo $?   # 0 ⇒ history preserved, not rebuilt
```

A commit whose message belongs to a different issue, or an old head that is no longer an ancestor, means the sweep rebuilt the tree rather than rebasing it. On a **closed** PR that is harmless and stays where it is — say so instead of ordering a third shape. On an open one it is a duplicate of unmerged work and must be dropped before anyone reviews it.

## Every dispatch states the assignment; every bot states its state
A bot that has not been told the assignment invents one, and a bot that does not report cannot be delegated to. So every dispatch names: the **id** (issue or PR), the **scope** (what to change), what is **not** in scope, and the **exact thing to report**. And every dispatch asks for a status line in one fixed shape:

```
BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>
```

A report without an id, a branch or a run id is not a report — it is a mood. When a bot reports work I did not dispatch, that is the first thing to reconcile, not the last: it means two lanes are on one issue or a lane has invented scope. Repeat the status request in every follow-up until the bot answers in that shape, and carry the current assignment in the message rather than expecting it to remember.

## Rerun never re-push; a PR under review is frozen
A run that ended `cancelled` at a head with no successor is repaired with `gh run rerun <id>` (same sha, no new commit). Pushing again cancels the rerun too and burns a whole matrix; each force-push on a queued PR costs ~25 jobs and discards any successes already paid for. Never cancel a run that is mid-flight and two-thirds green just to rebase — let it complete and report the verdict at that head first.

**A rerun is only permitted on a completed run.** While a run is in flight, both forms refuse:

```
gh run rerun <id>                                    # "cannot be rerun; This workflow is already running"
gh api -X POST .../runs/<id>/rerun                   # 403 {"message":"This workflow is already running"}
```

So for a *hung* in-flight run the only lever is `cancel` — which destroys its successes — and "just rerun it" is not an available action. Distinguish hung from slow by the step timestamps: four steps finishing in 27 seconds followed by 50 minutes inside one step with no transition is hung, and the honest report says so with both numbers. **Check `gh pr view <n> --json state,mergedAt` before any rerun or cancel** — a merged PR's run is history, not work, and rerunning it spends a matrix to prove something nobody will read. The durable fix is the deadline: a job with no `timeout-minutes` inherits the platform default (six hours on GitHub), so "hung" and "slow" stay indistinguishable and a held runner is invisible. File the timeout gap as its own issue; do not try to schedule around it.

**A caller's ceiling must exceed the longest job it calls, and the relation needs a test in both directions.** Adding a
`timeout-minutes` to a reusable-workflow caller is the easy half; a caller ceiling *tighter* than its callee kills a
healthy job mid-step and looks exactly like a legitimate timeout, while a callee with no ceiling at all makes the caller's
number meaningless (a six-hour default behind a 60-minute caller). Set the caller above its slowest callee, and pin the
relation (`caller.timeout > max(callee.timeout)`) so the next person who raises a job remembers the caller. A job that
has never completed in the sample gets no ceiling from observation — say so and derive the bound from the closest
analogue instead of inventing a number.

**The fix landing and the freeze are one event.** With `concurrency: group: <workflow>-<ref>` and `cancel-in-progress: true` on `pull_request`, the next push to the same PR always wins: a run can sit ten jobs green with the deciding job eight minutes into its suite, and a three-line push kills it. So a fix followed by a cosmetic push buys a cancellation, not a verdict. When a lane pushes while a run is live, name the cost with the timeline (`started 17:06:58 → push 17:10:10 → cancelled 8m44s in`) and restate the rule as one event — **the fix and the freeze go together, nothing rides along.**

So **a PR under review gets no cosmetic pushes**: batch review feedback into one push after the current verdict lands, and put text-only changes in a comment. When a bot amends a PR repeatedly, the honest diagnosis is not "CI is broken" — it is that the head moved before any run could finish, so no run will ever be cited. State that, name the sha to freeze at, and ask whether a push is genuinely needed before allowing one.

**Verdict the superset, never force a rewind.** When the last push before the freeze added only what you asked for (a missing pin, an exit code), that head is a strict superset of the one you froze and the right call is to verdict **it** — going back is a force-push, and a force-push is a push, so "restore the frozen sha" spends a matrix to arrive at a tree that is strictly worse. Confirm it only adds the requested work (`git diff <frozen> <new> --stat`, or check the files), then say plainly that the sha you verify is the sha that merges. The property that matters is *the verified tree is the merged tree*, not *the sha has a particular value*.

**Compare the tree before you decide what a moved head cost.** A re-push can be metadata-only or a real change, and the two have opposite consequences:

```bash
gh api repos/<o>/<r>/commits/<old> --jq .commit.tree.sha
gh api repos/<o>/<r>/commits/<new> --jq .commit.tree.sha      # identical ⇒ nothing was re-proven
```

Identical trees mean the cancelled run's successes still describe this code — the missing thing is a **conclusion**, not a result, and nobody should present the cancellation as "the code changed, the greens are void". Different trees void them, and a *commit rewrite* (an author fix, a rebase) changes the tree even when the diff is empty. Also check `parents`: a commit whose parent is the default branch rather than the previous head was rebuilt from scratch, not amended.

**When the same requirement is missing at successive heads, stop re-briefing in prose.** Rephrasing a demand a lane
has already ignored twice is the mistake; a measurement per head is not. Fetch the file from each ref and run it, then
post the table:

| head | empty diff | unknown path | pin in tests |
|---|---|---|---|
| `<sha>` | exit 2 | exit 1 | 0 |
| `<sha>` | exit 2 | exit 1 | 0 |

Then: **apply exactly this, prove it with these four one-liners, push once, freeze.** Paste the commands whose output
the lane must return (`jobs >/dev/null; echo $?` …), because a requirement stated as behaviour keeps being satisfied
"in spirit" while the exit code never changes. Four heads in one hour with the same two items open is a process finding
to name out loud — *"you have pushed four times and neither item moved"* — and then the rule: if either item is wrong
on the merits, argue in one message and the planner rules; do not push.

**Read the commit message of the next head, not only its diff.** A lane that disagrees with the ruling will encode the
opposite contract in prose — "no paths → exit 2, so the check is loud rather than quietly green" against a ruling that
says exit 0 — while the diff adds tests and docs. That is a disagreement, not an oversight, and it will not resolve by
re-briefing: state the ruling once more with the issue row that carries it, then take the branch off the lane rather
than negotiating through a sixth push.

**When the second proof table still shows no movement, take the branch off the lane.** That is what the table exists to trigger, and it is not a judgement of the lane's competence — a lane can add good tests for an hour and never touch the two lines the verdict waits on. Two messages, in this order:

1. **Stand the owner down explicitly**: no more pushes, no re-cut, no comments on that PR, and name what stays theirs so it does not read as a demotion.
2. **Hand the exact diff to a different implementer**: branch, PR number, current head sha, the lines with file and line reference, the proof commands, and *one push then stop*, in a worktree off that branch rather than the primary checkout.

Two lanes on one branch is the collision this avoids; one lane on it too long is the failure it fixes. Say which is which in both messages — the stand-down reads as blame unless it is framed as "the queue is not yours any more".

## A mechanism change ships with a verification issue
When a change alters which work CI does (path filters, class gates, skip lists), the accompanying issue must prove it with **one real change per file class**, each row backed by a run id, and the architect / implementer / tester split the work. Shape, row set, negative controls and probe hygiene: `references/verification-issue-design.md`. The one always-on rule from it: **expectations are derived from the classifier code, never from the workflow YAML** — if both sides come from the same file, the test agrees with the bug.

## Interrogating a filter: every subcommand must agree

A classifier with more than one entry point (`classify` for humans, `jobs` for the pipeline) can disagree with itself, and whichever one a workflow happens to call then decides whether a missing case is visible. Before accepting "it fails closed", run **each** entry point against the same bad input and compare **exit codes**, not messages:

```bash
python3 scripts/ci_scope.py classify --paths totally/unknown.file; echo $?   # 0 today = silent
python3 scripts/ci_scope.py jobs     --paths totally/unknown.file; echo $?   # 1 = wide + red
```

Two rules follow. **Failing closed means over-selecting *and* exiting non-zero** — selecting everything keeps the pipeline safe, the non-zero exit is the alarm, and a subcommand that widens silently has lost half the control. And **an empty argument must equal an absent one**: `--paths ''` exiting 1 while `--paths` (no flag) exits 0 turns a legitimately empty diff into a red for whoever writes `--paths "$CHANGED"`. **The empty case and the unknown case are not the same contract**, which is where a lane will argue with you for an hour:

| input | selection | exit | why |
|---|---|---|---|
| empty diff | every family | **0** | nothing for a human to fix; a red here fires on the mechanism's own triggers (`merge_group`, `workflow_dispatch`, a force-push that nets to nothing) and the author cannot clear it without inventing a change |
| path matching no class | every family | **1** | the pipeline is safe *and* somebody must add the glob — the alarm is the actionable half |

Put that table in the issue, the PR and the review brief. "It prints the full selection" is not the requirement: the exit code is what the check reports as red or green, so a run that widens and still exits 2 is fail-closed wearing fail-open's clothes. Test the exit code, not the message.

**Name the entry point, not just the expected number.** The same classifier can be right at the CLI and wrong in its
library: a fail-open widening implemented in `main()` (which swaps in `wide()` for an empty or unclassifiable diff)
leaves `scope([])` returning the small, unsafe selection, and the CLI's correctness makes that invisible — both are
"the classifier" to a reader, and only one is right. So every expectation states **who calls it** ("measured via
`jobs --paths`", not "the classifier returns"), and any caller a future change is likely to reach gets the safe answer
by default: move the decision *down* into the library function and let the CLI render what it returns. When two entry
points disagree, one of them is a defect — never a documentation nuance.

**A pin asserts behaviour, never a source spelling.** A guard written against `${{ github.base_ref || 'main' }}`
false-reds a correct implementation written as `BASE_REF="${EVENT_BASE_REF:-main}"`: two spellings, one behaviour, and a
test that cannot tell *absent* from *differently spelled* fails a fix that works. Write the assertion against what the
script does (does a dispatch run still compute a base? does it exit 0?) and only pin the literal text when the literal
is itself the requirement. A guard that rejects correct code is worse than no guard, because it teaches the lane that
the test is noise — and the repair is to publish the false red, not to quietly widen the regex.

**Never assert a list the tree is meant to extend — subset, not equality.** Manifests, rosters, workflow sets, job
lists and profile registries grow by design, so `assert names == ["a", "b"]` reds on the next legitimate addition and
teaches the next person to edit the test instead of the code: four separate instances in one night (a `.PHONY` set, a
`run.status` assumption, an inline→make call, and a manifest that four lanes were each appending a profile to). Write
`assert expected <= set(actual)`, and pair it with a referent check so a typo cannot hide — every listed name must
resolve to something real (`agents/<name>/SOUL.md`, a real job id, a target with a recipe). Subset for growth, referent
for correctness, never equality.

## The requirement lives in the issue, not only in your ruling

When a lane and the planner disagree about a contract, the argument ends where the issue states it — and if the issue
is silent on the half in dispute (it names the *selection* but not the *exit code*, the *scope* but not the *failure
mode*), the dispute is the issue's fault. Patch the issue row the same turn to name both halves, then quote that row in
the hold and in the brief:

> full pipeline, **fail open**: selects every family **and exits 0**; a path matching no class selects every family
> **and exits 1** — the glob is the human's half.

A hold anchored in the tracker survives a change of reviewer, a change of lane, and a planner who leaves. A hold
A hold anchored in "the planner said so" is re-litigated by the next agent that reads the code and disagrees.

**An acceptance criterion names behaviour, not a shape.** "`make ci-docs-gates` exists" cannot be ticked by a correct implementation that runs the same seven gates as steps of an existing job — and it manufactures a phantom deliverable, because a documented `##` target owes a docs row too. Write the outcome instead ("the docs class runs its gates, whichever shape"), name the commands that actually run, and when the shipped shape differs, record the absent target as **correct, not a gap** so the next reviewer does not file it as unfinished work. A box nobody can tick is worse than a criterion that names the behaviour.

## Read the failure before theorising — CI logs are available

A red job's assertion text is one command away, and believing otherwise turns a one-command diagnosis into hours of
speculation across lanes:

```bash
gh api repos/<o>/<r>/actions/jobs/<job_id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E 'FAILED|Error|^.*E   ' | tail -20
```

Without `--allow-escape-sequences` the response is a **`gh` guard message**, not an empty log — a few dozen bytes that
read as "logs unavailable" and get reported as an API limitation. `gh run view <id> --log-failed` is a second trap in
the same direction: it refuses while the **run** is in flight even when the **job** has completed, so a finished
failure looks unreadable. Get the job id from `gh api .../runs/<id>/jobs` and read that job's log directly.

Why it matters at dispatch level: the log names the failing test, so **a board of red PRs can be one shared cause** —
six stale assertions inherited from a merged change look like six independent lane bugs until one log read shows the
same six names on every PR. When several PRs are red, read one log before briefing a single lane, and check whether the
same failure reproduces on the default branch: a failure that exists there belongs to no PR and is fixed once.

**A log is evidence about the ref it ran on — name the branch, not just the sha.** A failing job read from
`fix/whatever` says nothing about `main` until you check the tree the job ran against:

```bash
gh run view <id> --repo <o>/<r> --json headBranch,headSha
gh api repos/<o>/<r>/contents/<path>?ref=<headBranch> --jq '.name'   # does this file even exist on main?
git -C <repo> ls-tree origin/main <path>                              # empty ⇒ the defect arrives WITH the PR
```

Measured case: a failure naming `<workflow>.yml` and a roster test was filed as "a red gate on main that no lane owns"
— the file existed on no default branch at all, it arrived with the open PR that introduced it, and the test did not
exist on `main`. Quoting a branch log as a repo fact converts a PR defect into a repo defect and hands it to the wrong
owner. The sha-in-the-finding rule needs the **ref** beside the sha, and the correction belongs on the issue
("this is `<PR>`'s branch, that PR owns the fix and it must land before the merge"), not in a DM.

**When you change a shape, grep the tree for tests that pin its spelling.** Replacing an inline script call with a
`make` target is the right fix and can still red the suite, because a *different* test pins the old inline text
(`assert '--event "${{ github.event_name }}"' in step["run"]`). After a workflow or graph shape change, search for
assertions that quote the old form before pushing, and assert the new **wiring** (target name, env var names, the
Makefile's call to the script) rather than the exact command line. A change that fixes one stale assertion and breaks
another is the same defect twice.

## Report verdicts, not run counters
Polling turns into narration fast: `18 success · 2 running` is not news, and a turn spent re-reading it is a turn not spent measuring something that could change a decision. Report a run **only** when its conclusion changes, and then as a verdict (`SUCCESS`/`FAILURE`/`cancelled at attempt 2` with the run id and the head sha). While waiting on runners, verify an invariant instead — that two trigger lists are identical, that a guard fails when broken, that a branch really exists — and report that.

**Quote a completed run's total, never a snapshot.** Rows gated by `needs:` are created as their dependencies resolve, so an in-flight job count is a **lower bound that grows under you** — a run can show 19 rows while `engine-matrix` is queued and 25 by the time it completes. Any argument about cost ("this two-file diff still paid for four base toolchains") has to be made against the completed total, with the run id attached; a mid-flight number makes a true claim look inflated and hands the other side a free rebuttal.

## A filter, its twin and the classifier are one set

A workflow filter must match the classifier's **class**, not a file extension. `**/*.md` in `paths-ignore` silently skips `ci.yml` for `data/trending-README.md`, `.hermes/skills/**/SKILL.md` and `tests/fixtures/**/*.md`, none of which are docs. Prove a filter with the case that catches it (a markdown-data-only PR must still schedule the matrix), not with a docs PR, where the bug is invisible.

**Read the parsed list, never grep for the string.** A branch that documents its own bug will match the grep: `grep -c '**/*.md' ci.yml` returns 2 on a file whose `paths-ignore` is the correct five paths, because both hits are the comment explaining why a bare glob is wrong. Verify the way GitHub evaluates it — load the `on:` block (or the list under `paths`/`paths-ignore`) and test the paths you care about against it — and treat a string hit inside a `#` comment as evidence of nothing. The same trap applies to any "is X present" check on a file that discusses X.

**Assert the three sets are ONE set, not that they are compatible.** The trigger's ignore list, the companion workflow's `paths:` and the classifier's class must be equal three ways — `set(CLASSES[cls]) == set(ci.yml paths-ignore) == set(docs.yml paths)`. A classifier still matching `*.md` while the trigger holds five literal paths makes the *printed selection* lie about the trigger, and the printed selection is the only place a human sees the truth; a pin that only checks one pair leaves the third free to drift.

Two things every trigger change owes, both of which CI catches and reading does not:

- **A new trigger needs its dispatch-form annotation and its regenerated table.** A bare `workflow_dispatch:` fails `check-dispatch-forms` (a column-0 `# dispatch: no inputs — <reason>` line, plus the `docs/BOTS.md` row), and that gate runs inside `ci-unit`, so it reds `linux/unit`: a verdict blocker, never a lint nit.
- **Prove the trigger by running it.** `gh workflow run <scope>.yml --ref <branch>` yields a real run id and a log line naming the fallback (`No github.base_ref for event 'workflow_dispatch': reporting the diff against main.`); parsing the YAML proves only that the text exists. An event the repo cannot emit stays *"not exercised — no merge queue configured"*, which is a different sentence from "impossible".

And the meta-rule from both: **when CI catches a gate your local loop omitted, add that gate to the loop before the next push.** A green local run that skipped `check-dispatch-forms` means less than it looks, and the lane that reports it honestly is doing better work than one that reports green.

## A hold is board state; lifting one needs evidence

`do-not-merge` and work-queue labels (`agent:implement`) are **yours to change, not a lane's** — a lane stripping a label it disagrees with is indistinguishable from a lane editing its own backlog, and only you can see every lane's queue. When a lane finds a stale label, it reports; you remove.

The hold itself has two shapes and they need different handling:

- **A hold with an open reason** is doing its job: leave it, and ask the holder for the one-line unblock condition so the next reader knows what would clear it.
- **A hold with a closed reason is a blocker in disguise.** Once the stated defect is fixed, the label silently parks work that is ready and the PR looks blocked for a reason that no longer exists. Demand either a lift — with the removal itself evidenced (`check_pr_authors … → OK` at the reviewed head) — or a new unblock condition.

Check what a hold is actually gating before worrying about it: with auto-merge disabled or absent, removing `do-not-merge` hands nothing to a bot.

**A defect that cannot fire on any event the repo produces is a follow-up, not a merge blocker.** Before keeping a hold
for a missing trigger, a wrong exit code or a broken branch, list the events the repository can actually emit:

```bash
gh api repos/<o>/<r>/branches/main/protection                                  # 404 ⇒ no required checks
gh api repos/<o>/<r>/rulesets --jq '.[].id' | xargs -I{} gh api repos/<o>/<r>/rulesets/{} --jq '[.rules[].type]'
gh api repos/<o>/<r>/actions/workflows/ci.yml --jq '.path' >/dev/null          # then grep its on: block
```

No merge queue configured means `merge_group` never fires; no `workflow_dispatch` trigger means a manual run cannot
happen; a `pull_request`-only filter means the empty-diff branch is unreachable from any PR. Where that is true, the
defect is **latent**: lift the hold, land the verified part, and file the follow-up with its acceptance criteria and
negative control so the day the event appears, a test is waiting. Keep the two-sentence distinction explicit —
*"latent, tracked in <issue>"* is a decision, *"not satisfied"* is a blocker, and conflating them parks finished work
for a bug nobody can trigger. The inverse also holds: a defect that **does** fire on an ordinary PR (a gate that reds
`ci-unit`, a filter that skips a real path) is a blocker however small it looks.

## An approval the identity cannot give

In a fleet where every bot pushes on the owner's token, every bot-authored PR is authored by the **owner**, and GitHub refuses an approving review from the author's account:

```
$ gh pr review <n> --approve
Can not approve your own pull request
```

So `reviewDecision` can never leave `REVIEW_REQUIRED` on a bot-authored PR, `mergeStateStatus` stays `BLOCKED`, and a board reading "28 open, none mergeable" is describing an **identity constraint, not a backlog** — several of those PRs may carry complete review verdicts. Three rules:

- **A bot review is a verdict comment, never an approval.** Say it in the brief, so a lane does not spend turns trying to flip a state it cannot reach.
- **Make the verdict legible instead of faking the approval** — a fixed `VERDICT: approve | changes` first line, or a `reviewed:verdict` label with the reason and the unblock condition in the comment. Greppable by tooling, honest about what happened.
- **Never add a second identity to approve.** That turns one credential into an approval loop and is exactly the gate GitHub is protecting.

**But check whether the repo already has one before concluding an approval is impossible.** "No bot can approve" is a claim about identities, not about the fleet: read the merged PRs' reviews (`gh api .../pulls/<n>/reviews --jq '.[]|"\(.user.login) \(.state)"'`) and you may find a second account approving bot-authored PRs — in which case the merge machinery is already credentialled, usually as a PAT in a workflow secret (`secrets.<TOKEN>`). Two consequences. **Read the merge script before proposing an "approve step"**: a script with `APPROVE=1`, an `approve()` call and tests pinning "approver ≠ author" already does this, and a second `gh pr review --approve` reds a green PR with `422 already approved` — proposing it as "the missing piece" is a dispatch that would break what it claims to fix. And when the script still defers, the defect is a **condition**, not a missing step: compare the state it gates on (`mergeStateStatus`, `reviewDecision`, `mergeable`) against what the API returns at decision time, and read the run's own state line for that PR before changing anything. A `reviewDecision` that is empty rather than `REVIEW_REQUIRED` at decision time is a two-line fix with a test; a new workflow step is a rewrite of working code.

**Establish merge capability before you promise a merge.** An owner saying "approve and merge them all" is a grant you may not be able to execute, and discovering that one PR at a time wastes the turn:

```bash
gh auth status                                                              # the identity and, crucially, its SCOPES
gh api repos/<o>/<r>/collaborators/<login>/permission --jq .permission      # "write" ⇒ cannot bypass
gh pr merge <n> --squash --admin                                            # --admin is a no-op on write
```

Measured refusals, each naming a different missing thing: `Pull Request is still a draft` (mark ready first, `gh pr ready`); `At least 1 approving review is required by reviewers with write access` (HTTP 405 via REST, same message via GraphQL — a **rule** the token cannot read and therefore cannot bypass); `Can not approve your own pull request`. When the token's permission is `write`, `--admin` changes nothing and the bulk request must be answered with the two paths that actually work — **the owner clicks approve once per PR**, or **the review requirement is relaxed for the duration** (recorded, with a timestamp, on the tracking issue). Say which you need rather than retrying merges one by one.

**Also check the PR's provenance:** `gh pr view <n> --json isCrossRepository,headRepositoryOwner`. A fork-head PR is a different animal from a same-repo PR — approval and merge paths can differ, and a batch merge order should name which PRs are cross-repo.

Report the distinction, not only the count: *"no verdict yet"* and *"verdict posted, owner approval outstanding"* are different numbers, and only the second is waiting on the owner.

## A rule you cannot show on `main` is not a rule

Before enforcing any rule on a PR — a required body line, a hygiene gate, a label contract — prove the base branch
actually carries it. A gate described in an **unmerged issue or PR** is a proposal, not a gate, and demanding it turns
a clean PR into an apparent failure:

```bash
git -C <repo> show origin/main:scripts/check_pr_hygiene.py | grep -c 'AGENTS:'      # 0 ⇒ not a gate today
git -C <repo> show origin/main:.github/workflows/ci.yml    | grep -n 'paths-ignore'
```

When the grep is empty, say so and withdraw the requirement in the same message — "forward-looking, not a failure".
The same check applies to a reviewer's hold: **a hold whose reason a command cannot show is not a hold**, and pressing
for one costs a lane a turn and the board a false red. Rules arrive through merged code, so the enforcement date is
the merge date.

## Verify what you wrote, not that the write succeeded

A successful API call is not a landed document. Two ways this bites:

- **`gh issue create --body -` stores a literal `-`.** stdin is consumed only by `--body-file -` (or `-F body=@file`
on `gh api`). The issue is created, the command exits 0, and the body is one character.
- **A comment posted while another lane edits the same body can be overwritten** by their next PATCH.

So after every programmatic write, read the artifact back and check **shape and length**, not the exit code:

```bash
gh issue view <n> --repo <o>/<r> --json body --jq '{len:(.body|length), sections:[.body|split("\n")[]|select(startswith("## "))]}'
gh api repos/<o>/<r>/issues/<n>/comments --jq '.[-1]|{at:.created_at,len:(.body|length)}'
```

A six-section issue body reads ~2–9 KB; a comment reads ~1 KB. A body of length 1 is a missing document, and a
planner who reports "issue filed" on a 1-byte body has reported a title.

## An owner grant outranks a generic rule — including the no-merging rule

"Never self-approve" and "never merge without the owner" are defaults for a lane acting on its own initiative. Where the **owner has written a grant naming the PR, the action and the condition** ("once CI on this head is green, approve, remove the hold and squash-merge"), following it is obedience, not self-dealing: the PR author is usually a bot identity, and the approval step is named rather than inferred.

Two conditions keep it auditable: the merge comment **quotes the grant** (words, date, and the narrowed form any reviewer recorded), and the grant is tied to a **head sha** — if the head moves before the merge, stop and re-measure rather than landing whatever the branch became.

When a lane proposes to resolve such a standoff, prefer the **smaller action**: attempt the merge first, unapproved. If the repo's ruleset does not require review, nothing was self-approved and the question disappears; if it refuses, you have a refusal as evidence rather than a preference as an argument.

## The issue body belongs to whoever is refining it
Refining an issue and appending your verification criteria to it are not the same act. Two writers on one body is last-writer-wins with no merge — an append made while another lane's refinement was in flight simply vanished and the criteria with it. So: **planner input goes in a comment** ("criteria for the body owner to fold in"), and the body is edited only by whoever is refining the issue or by you when you own it. If a body does need to grow, say what you are adding in the same turn and check the byte count afterwards — `len(json.loads(gh issue view …)["body"])` before and after.

## Every count carries its limit

`gh issue list --json … --jq length` returns **30** because that is the endpoint's default page size, not because the
backlog shrank: measured 2026-10-28, the same repo read `30` with the default and **79** with `--limit 200`, while the
number had actually grown. Always pass `--limit` when counting (`--limit 200` for issues, `--limit 100` for PRs) and
say the limit next to the number, or the report invents a 35-issue cleanup that never happened.

## One builder per file, and prove no duplicate before you dispatch

When a change needs several lanes (classifier + workflow + tests), **assign by file ownership** and say who owns which
file out loud: the lane that owns the pipeline file edits the pipeline file, the design lane refines and reviews, the
test lane owns the checklist. Three lanes half-working one issue produces a design note, a library and no change.

Before dispatching anything, spend the two commands that catch an existing implementation:

```bash
gh pr list --repo <o>/<r> --state open --limit 100 --json number,title,files \
  --jq '.[]|select(.title+" \([.files[].path]|join(" "))"|test("<keyword>|<path>";"i"))|"\(.number) \(.title)"'
gh api repos/<o>/<r>/branches --paginate --jq '.[].name' | grep -i '<keyword>'
```

A second implementation of the same issue is worse than a late one: it manufactures the very file collision the lanes
were sequenced around. When one lands anyway, **close it as a duplicate with a file-by-file comparison table** (files,
+/−, which behaviours each covers), name the canonical PR, and say explicitly that the diagnosis was correct and
independently reached — a duplicate decision, not a rejection of the work.

**A rewrite is a push; a new PR is a decision.** When a branch needs a fix, the lane force-pushes the branch it already owns — one trail, one review thread. Opening a *fresh* PR for an issue that already has an open one is a decision for the planner, and a lane that does it has manufactured a duplicate by another route. Three vehicles for one issue in a single evening cost more reviewer attention than the change did, and each new branch re-cut the same tree. State it in every brief: *fix the branch you have; do not open a second*.

**Before authorising a fold, check the content is not already in the tree.** "Cherry-pick this commit onto the live branch" is a common ask and often moot: if the assertion or fix already exists under a different name, the authorisation buys a second test of one property plus a push to another lane's branch. Two commands decide it:

```bash
git -C <repo> merge-base --is-ancestor <sha> origin/<branch>; echo $?     # 0 ⇒ already an ancestor
git -C <repo> show origin/<branch>:<path> | grep -c '<the property>'
```

Write authorisations that survive that check — name the **property** to end up on the branch, not a commit to apply — so a lane that finds the property present can return the licence unused. Returning an unused licence with the reason is the correct outcome, not a missed opportunity: it costs nothing, and spending it on a no-op costs a run.

**When both drafts are the same infrastructure, the survivor is the one others stack on.** Two lanes implementing one
issue produce near-identical PRs (same skeleton, same scripts, one file count apart). The tie-break is not merit and not
diff size: count how many open PRs already base on each branch
(`gh pr view <n> --json baseRefName` across the board). Closing the branch four PRs stack on orphans all four and forces
four rebases against a differently shaped manifest — the divergence pattern again — so the stack wins and the duplicate
is closed, with its genuinely better halves (live-profile proof output, an extra make target, disclosed skill texts)
carried over as comments and a small follow-up rather than as a bigger duplicate.

**Pick the survivor by the regression test, not by diff size.** Two PRs that both fix a bug are not equal: the one
whose test *fails when the bug is reintroduced* survives, because the other one's fix lasts until someone tidies the
YAML. Check the guard directly before choosing — grep the new test file for the offending pattern and for the two or
three real paths that were silently skipped — and say which row decided it. Same file count and near-identical diffs
are the normal case; the guard is the only discriminator that matters after merge.

**A lane told to review that ships an implementation is a process finding, not a gift.** Name it in the same message
that accepts the better artifact: the correct move was "this branch cannot meet the criterion, here is why, hand it to
me", not opening a competitor. Otherwise the next pass gets two of everything again.

**But read your own dispatch before you say "unrequested".** Before calling a branch a rival, find the message that
started it: an earlier instruction to *implement* one issue at all costs is an assignment, and a second lane opening a
similar branch later does not retroactively turn the first into a rogue. **And check the authorisation record before
saying a licence never existed** — the grant may be a comment you wrote on that very PR an hour earlier while its inbox
was `queue_full`:

```bash
gh api repos/<o>/<r>/issues/comments/<id> --jq '"\(.issue_url|split("/")|last) \(.user.login) \(.created_at)"'
gh api repos/<o>/<r>/issues/<pr>/comments --jq '.[]|select(.body|test("AUTHORIS|authoris|authoriz";"i"))|"\(.created_at) \(.body[0:80])"'
```

A licence written to a branch by name, hours before a freeze conversation moved on, is exactly the kind of grant a
planner forgets owning — and "you were never authorised" when the comment exists inverts the incident and lets the
real overstep (pushing content other than the authorised commit) go unnamed. Check the ordering — which existed first, the
dispatch or the other PR — and if you got it wrong, correct it **in the PR trail**, not only in a DM: a wrong accusation
left in the record teaches every future lane to ignore a real one. The fair criticism, when it applies, is narrow and
forward-looking ("once the other branch appeared this should have switched to review-only"), never a characterisation of
the whole run.

## The commit identity is part of the artifact

A repo that allowlists commit identities (`scripts/check_pr_authors.py`, `ALLOWED = {"Name": "email"}`) reds
`linux/unit` for any commit authored off-allowlist — so an identity defect is a verdict blocker, not a nit, and it is
invisible in a diff. **Measure every open PR's head at once, not the one PR you suspect:**

```bash
for n in $(gh pr list --repo <o>/<r> --state open --limit 100 --json number --jq '.[].number'); do
  h=$(gh pr view $n --repo <o>/<r> --json headRefOid --jq .headRefOid)
  e=$(gh api repos/<o>/<r>/commits/$h --jq '.commit.author.email')
  echo "$n $h $e"
done   # diff against the allowlist
```

A lane reporting "all my commits carry the wrong address" deserves that board-wide number before anyone schedules
re-authors: usually the bad commits never reached an open PR's head (they live on closed branches, or a rebase re-authored
them), and exactly one PR needs the fix. **Re-author nothing by default** — set the address in the tree instead, so the
wrong one cannot be the default:

```bash
git -C <repo> config user.name "<allowed name>"
git -C <repo> config user.email "<allowed email>"   # repeat per worktree; `-c` flags are forgotten, config is not
```

**A force-push from a stale worktree overwrites another lane's repair.** `--force-with-lease` is only as fresh as the
ref you fetched: it protects against strangers, not against your own older knowledge, so a push from a tree cut before
someone else repaired the branch passes the lease and silently discards their commit — including a corrected author and
the lines that made the branch green. Fetch immediately before any force, use `--force-if-includes`, and **never
force-push a branch another lane repaired**. When it has already happened: compare trees (`gh api
repos/<o>/<r>/commits/<sha> --jq .commit.tree.sha`) to say what the greens still describe, name the lost content from
`git diff --stat <discarded> <tip>`, and if the PR is closed leave it dead rather than spending another matrix to
repair a branch nobody can merge.

## A worktree is not storage

Uncommitted work in a worktree is a file nobody saved: a branch switch, a sweep or a container error empties it. So
**commit and push before the lane touches anything else** — in every brief, as a preflight line, not advice — and
insure an unpushed branch (`git format-patch <base>..HEAD -o <scratch>/` plus
`git bundle create <scratch>/<n>.bundle <base>..HEAD`). Proof of survival is the worktree and the remote sha, never the
claim. Detail in `references/fleet-failure-modes.md`.

## A new worktree inherits the checkout it was created from

`git worktree add` branches from the **current checkout of the repository it is run in**, not from `origin/main`. On a tree whose primary directory is parked on someone else's PR branch, every worktree created there starts on that branch — and the result is a branch whose tree is byte-identical to another PR's head, with all of its own work sitting uncommitted while the lane believes it is building off main.

So the brief carries two checks before the first edit, and the planner carries the same two when inspecting a lane:

```bash
git -C <worktree> rev-parse --abbrev-ref HEAD        # the branch the task owns, not someone else's
git -C <worktree> log --oneline -1                     # parent should be origin/main, not another PR's tip
```

Keep the primary checkout on `main` and clean, and say so in every brief: it is the workspace other lanes read as `origin/main`. **One worktree per PR.** Reusing a worktree for a second branch is how a one-file change becomes an unrelated diff: the
second edit lands on the first branch's tree, and only `git rev-parse --abbrev-ref HEAD` before the first edit catches
it. Cut a tree per branch, or check the branch name immediately before writing; a lane that discovers it edited the
wrong branch after committing has to unwind a push, not an edit.

A branch that aliases another PR's tree is not a rebase problem, it is a wrong-parent problem, and the recipe is `add` → `commit` → `checkout -B <branch> origin/main` → `cherry-pick` → `push`, never a re-implementation.

## Two dispatchers, one bot

When a recurring tick and an interactive session both orchestrate, they will hand one bot different orders — the
tick queues twelve items while you strip the queue to one, and the bot follows whichever arrived last. Reconcile by
naming the order once, in writing, to that bot (*"this supersedes the earlier brief: #X only, everything else is
parked"*), and keep the tick out of lanes that already have an order. Two orchestrators is the same failure as two
builders: duplicated, contradictory work that looks like activity. See `references/fleet-failure-modes.md`.

## A closed PR stops tracking its branch

Closing a PR is a decision, not a bookmark: the PR freezes at the sha it had when it closed, and the **branch ref keeps
moving independently**. A lane that fixes a closed PR's branch, or pushes a `--force-with-lease` to it, produces work
nobody can see — the PR still shows the old head, and any "verdict" cited from it describes a commit that will never
merge:

```bash
gh pr view <n> --repo <o>/<r> --json state,headRefOid,closedAt   # state CLOSED, headRefOid is frozen
gh api repos/<o>/<r>/commits/<branch> --jq .sha                  # the ref has moved on
```

So when you close a PR as superseded: say in the close comment **where the work continues** (the surviving PR or a new
one), and tell the author in the same message that further pushes there are invisible. And when a lane reports progress
on a PR you closed, believe the `state`, not the report — the honest sentence is "that branch moved; the PR did not".
Both halves are the same rule: **the artifact that counts is an open PR at a sha you measured**, never a branch.

## A stacked PR runs no CI at all

A PR whose **base** is another feature branch produces **zero runs** in this repo, because every workflow gates on `on.pull_request.branches: ["main"]`. An empty checks tab then reads like "not started yet" and a lane can wait an hour for a verdict that will never exist:

```bash
gh pr view <n> --json baseRefName          # not "main" ⇒ no workflow will trigger
gh run list --branch <head> --limit 3      # empty on a PR that has been open for an hour
```

So a stacked PR is a review artifact, never a verdict. Either **retarget it to `main`** (it then carries the base branch's whole diff, i.e. it supersedes rather than stacks) or **fold it** — cherry-pick its commit onto the branch it was stacking on and close it. Say which in the PR, and never let a lane sit waiting on checks that cannot arrive.

**Dispatch is how you exercise a branch that cannot get PR CI.** `gh workflow run <workflow>.yml --ref <branch>` executes that branch's workflow on demand, at no commit cost, and is the only way to prove behaviour that no `pull_request` run reaches — a dispatch-only trigger, a `base_ref` fallback, an always-on reporter. It yields a real run id and a log line (`No github.base_ref for event 'workflow_dispatch': reporting the diff against main.`) where parsing the YAML proves only that the text exists. Keep it next to "rerun, don't re-push": both are cheaper than a push for learning the same thing.

## Before you say "it is missing", name the search scope

A missing-symbol claim is the cheapest way to look rigorous and be wrong, and it sends a lane to rewrite work that already exists. Measured case: `grep -c merge_group tests/test_ci_scope_trigger.py` → 0 was reported for several consecutive heads as "the behaviour landed and nothing pins it" — while the pin sat in `tests/test_ci_scope.py` (the module that holds the classifier's contract), and the file that was grepped deliberately holds a different invariant.

So a "missing" report carries three things: the **exact command**, the **scope it searched** (`tests/` as a whole, not one filename), and the **line** where the thing would have to be if it existed. When modules split by convention — behaviour with the contract, source-text invariants in their own file — grep the directory first and read the hit before concluding:

```bash
grep -rn "merge_group\|workflow_dispatch\|EVENT_BASE_REF" tests/ | head   # the tree, not one file
```

Two consequences. **A pin already asserted elsewhere is not a follow-up** — filing it again puts a second assertion of one property in a second module, which is how two modules start drifting. And when you have already filed it on the wrong grep, **close the issue and record the measurement error on it** rather than leaving a phantom deliverable for the next pass to chase.

## Route a freeze through the PR, and read the PR before every push

A lane's inbox is not the only place an order lands, and `queue_full` means the DM is still in a queue: a freeze posted as a **PR comment** is in force from its timestamp, not from when the lane reads it. So the lane's pre-push check is `gh pr view <n> --json comments` (or the last comment's `created_at`), and the planner's rule is to post the freeze on the PR **first**, then DM — never the reverse.

When a timeline is disputed, compare like with like: `PR freeze 17:14:59 → push 17:18:33 → DM 17:20` means the push came 3½ minutes after the freeze and 90 seconds before the message. Say which artifact you are quoting ("the PR freeze"), because "the freeze" is exactly the ambiguity that turns a fair call into an accusation of the wrong lane.

**Convert a hold into a trigger, not a promise.** A release condition a lane must *remember* (“open the next PR when the run finishes”) decays into "whenever I next look". Ask for it self-executing — a background watcher on the run id that wakes the lane on conclusion, green or red — so the moment is not a human's memory. Same principle as replacing "rerun later" with a scheduled check.

## Prove a guard by sabotage, not by its existence

A test that has never been seen failing is decoration. The proof a guard actually guards is a three-step loop, run on
the branch and reported as output rather than as confidence:

```bash
# 1. reintroduce the defect the guard is supposed to catch
#    (the bad glob into paths-ignore, the old exit code, the stale launcher tag)
make test-<suite>        # expect RED, and note HOW MANY cases fire and WHICH ones
# 2. restore the file
make test-<suite>        # expect GREEN, 0 failures
```

Two properties make the loop worth demanding. **Several independent assertions should fire, not one** — a single red
case means the invariant is pinned in one place and a refactor of that file removes the guard. And **at least one of
them should compare two artifacts by value** (the trigger list against the classifier's class, the launcher tag against
the digest the writer computes), because a test that only greps its own file cannot notice the two drifting apart.

Apply the same loop to anything a lane claims as "guarded": ask for the red run, not for the test's name. When the
lane reports a false red it produced itself (its pin rejected a correct implementation), the repair is to publish the
false red and re-assert the **behaviour** — a guard that fails correct code teaches the next contributor to break the
code until the test is happy.

## When one job gates every verdict and proves nothing new

A platform row that duplicates a cheaper row is not just expensive — it becomes the longest pole on every PR, and the
verdict waits on it while the run looks green everywhere else. Before proposing a removal, measure what it uniquely
covers:

```bash
gh run view <id> --json jobs --jq '.jobs[]|"\(.name) \(.conclusion // .status)"'   # which row is last, how often
```

If the row re-runs the same suite another platform already runs, the fix is a **scope change, not a deletion**: drop it
from `pull_request`, keep it on `push` to the default branch (one run per merge still catches platform regressions),
and make it opt-in per PR through a label or the workflow's existing selection input. Record the coverage trade in the
repo's bot/CI docs and state it in the issue, so the absence is a decision a reader can find. `test_no_ci_step_or_job_is_skipped`
forbids a job-level `if:`, so use the selection-input pattern the repo already has rather than adding a conditional.

**When the rows are not reliably issued at all, delete the stage — do not gate it.** Gating and opt-in are for a row that costs time; they are useless for a row that may never get a runner, because a conditional row still holds the matrix open. Classify first (`runner_name` present or not, across many runs, with a cheap control leg in the same probe), and if the pattern is "never issued a runner", the fix is removal from the `pull_request` path in one deletion — no job-level `if:`, no placeholder row, and the statement of what coverage is lost. Two consequences worth carrying: **a matrix with no long-tail rows still needs its premise re-measured** — job-selection optimisation built to avoid a platform's queue may be worth nothing once that platform is gone, so re-read the justification before dispatching the optimisation; and **the removal can unblock work it never touched** (a stage that stalled every PR was also the reason a dozen others sat `pending`), so check the board again the moment it lands.

## A dispatch must not prescribe a mechanism that does not exist

Naming "use the existing X pattern" in a brief is a claim about the tree, and a lane that trusts it builds the wrong thing or stalls. Before the words leave the message, prove the mechanism exists at the base the lane will cut from:

```bash
git -C <repo> show origin/main:.github/workflows/pipeline.yml | grep -n 'inputs:'   # the pattern, or nothing
git -C <repo> show origin/main:.github/workflows/ci.yml      | grep -n 'matrix:\|with:'
grep -rn '<make-target>' <repo>/Makefile
```

Measured case: a brief said "use the existing selection input" for hiding CI jobs — the base had `inputs: runner, optional` only, and the thing being copied was a *matrix row placeholder*, which can remove a row inside one job but **cannot remove a job**. A placeholder cannot stand in for an omission; only a separate workflow, a selection input that emits a `none` row, or a forbidden job-level `if:` can. When the pattern is absent, do not improvise one in the brief: state the goal, name the constraint (`no job-level if:`), and ask the owning lane for the design. A lane that answers "the pattern you named does not exist, here is the shape that fits the repo" is doing the dispatch's job correctly, and the right reply is to adopt its design — not to repeat the original wording.

Corollary: a mechanism copied from a *stacked* PR is not on the base either. Read the file at `origin/main`, never at another PR's head.

## When the owner broadens an instruction, supersede rather than amend

An owner instruction rarely stays the same size: "disable the three slow rows" becomes "no more mac runners, disable the stages". Amending the original issue in place hides the escalation and leaves the narrower issue, its comments and its branch all asserting a smaller scope. The shape that keeps one trail:

1. **File the broader issue as the umbrella**, quoting the new instruction and carrying over the measurements that justified the narrow one.
2. **Close the narrow issue as superseded**, with a comment saying exactly which parts carry over (rationale, caveats, the no-`if:` rule) and where — never just "superseded".
3. **Narrow any adjacent issue** that overlapped, in one comment, so two issues cannot both claim the same rows.
4. **Re-point the vehicle, do not open a second one:** the in-flight branch and its worktree move to the umbrella issue. Say so in the brief, and tell the lane to drop any partial design the narrower scope produced.
5. **Say which parts are now parallel:** a deletion that touches only one group of jobs is not blocked by an unrelated PR landing, and unblocking it in writing is often the fastest win available.

A supersession is a board decision you make and record; leaving both issues open invites a second vehicle for a scope that no longer exists.

## A deferral is a decided close with a measured reopen bar

When the owner says a line of work is *not needed yet* (its pressure disappeared, or the measurements a decision needs do not exist), the correct artifact is a close that a future reader can act on — not a PR left open, and not a hold with no exit:

1. **Close the PRs** with a comment that says what changed underneath them (the merge that removed their motivation), what is preserved (head sha, the tests, the negative control, the verification pair), and that it is **deferred, not rejected on merit**.
2. **Label the issues** (`do-not-merge`) and comment the same reasoning, so the label and the prose agree — a label whose reason only exists in a DM is re-litigated by the next reader.
3. **Write the reopen condition as a measurement, never as a feeling**: how many runs of which kind, then which numbers to compare, then which result makes the work the fix. "~20 Linux-only `pull_request` runs after <sha>, then compare job count and wall-clock per change class" is a bar; "when it becomes a problem" is a mood.
4. **Say which related items are *not* held** — a defect that made the work unreadable (a missing timeout, a broken guard) still deserves to land, and lumping it into the deferral parks a real fix.

Deferring is a decision you make and record; a PR left open under the old premise costs a reviewer an hour and teaches nobody why it stopped mattering.

## Pitfalls

- **A claim with no branch is theatre.** The 3h TTL blocks every other implementer from the issue that may be
  reddening all PRs. Release it in a comment with the 404 as evidence, then re-dispatch.
- **Never enumerate claims with `gh issue list --search`.** The search returns a subset, so a live claim is
  invisible and the pass dispatches a second implementer onto work that is already in flight. Read *every* open
  issue's comments and regex the marker, then compare it to the branch list:
  `gh issue list --state open --limit 200 --json number,comments --jq '.[]|.number as $n|.comments[]|select(.body|test("bot-claim:"))|"\($n) \(.createdAt) \(.body)"'`.
  A claim whose `run=<id>` already reports verdict `implement` + `PR: #<n>` is live work, not a dispatch target.
- **A finished `refine` run leaves a live-looking claim.** `run=<id>` completed `success`, verdict `refine`, no
  branch, TTL still counting: the issue is unowned. Release and hand it to the specialist for its class — the CI
  bot will not pick it up again inside the TTL.
- **Never run a prune to "tidy up" before a dispatch.** The worktree you would delete is often the in-flight work; the
  destructive target is owner-only (#794) and a bot following `AGENTS.md:483` literally destroys its own run.
- **Deleting a branch whose issue is open throws away the only work product.** Check
  `compare/main...<branch>` first: 1 commit and a few behind is salvageable (hand it over to finish the PR); far
  behind across generated files is a rebuild, so delete and re-implement fresh.
- **An issue with an open PR is not dispatchable work.** Before handing an issue to an implementer, check
  `gh pr list --state open` for a PR whose body closes it; a second branch for the same issue is a duplicate artifact,
  and the correct instruction is "do not implement this, it is in review".
- **An automated approval is not the owner's approval.** A PR can show `reviewDecision: APPROVED` and be merged by the
  same non-human identity seconds later — read `gh api .../pulls/<n>/reviews` (`submitted_at`, `user.login`) against
  `mergedAt`/`mergedBy`. When approve and merge come from one identity inside a few seconds, report it to the owner as
  an incident; never present it as "your approval was given".
- **Labelling everything `agent:implement` floods a 3/day bot** and builds a queue nothing drains — especially while
  its implement leg is broken. Order the queue, label the head of it.
- **A `success` run can be a decision with no artifact.** A CI triage leg that returns `refine` posts a restated spec,
  labels the issue refined, opens no branch and still exits green. Treat that issue as unowned and hand it to the host
  implementer; never read `success` as “being worked”. Check the verdict comment and the branch list, not the run's
  colour.
- **Two lanes converging on one gap is a sign the gap is real — and still one issue too many.** When a second issue appears minutes after yours describing the same defect, close the duplicate rather than merging the prose, but **read it first**: the newer filing often carries a criterion the survivor lacks (a failure mode, a second direction of the same check, a negative control). Fold that into the survivor as a supplement comment, name which issue keeps the trail and which acceptance criteria came from the closed one, and say plainly that two lanes reaching the same measurement is evidence for the gap rather than a mistake by either.
- **Append to a workspace file, do not keep the fleet state in your head.** Write the run/claim/branch snapshot to a
  JSON file and diff it on the next pass: a bot that was quiet last pass and is still quiet is a finding.
