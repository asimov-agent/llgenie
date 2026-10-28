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

A bot is idle when it has no run inside its slot, or when its recent runs are all `skipped`. **`skipped` is the
signal that matters**: `issue-bot` skips the implement leg on a `refine`/`close` verdict, so a green run can mean
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

A host bot with nothing on the repo may be working or may be spinning, and the difference decides what you send next.
Measure its own profile, not the repo:

```bash
stat -c '%y' ~/.hermes/profiles/<profile>/state.db                 # last write = last activity
tail -5 ~/.hermes/profiles/<profile>/logs/agent.log               # "API call #N" = how many turns burned
git -C <its worktree> log --oneline -1; git -C <its worktree> status --porcelain | wc -l
```

A live session with a high turn count, an unchanged branch tip and a fixed set of uncommitted paths is a loop, not
progress. Breaking it is a dispatch problem, not a persuasion problem:

- **Reduce the brief to the exact commands**, one fenced block: `git add -A && git commit -m "…" && git fetch origin &&
  git rebase origin/main && git push origin HEAD:<existing branch>`, then the `gh pr create` line. No gates, no
  analysis, no options — a looping agent asked to choose will choose to explore.
- **Remove the unreachable gate.** A local suite that cannot finish inside the agent's terminal cap will never go
  green; say "CI is the referee, commit and push" and name the CI duration so the instruction is checkable.
- **Move the specialist-shaped slice elsewhere** (see 2b) instead of queueing a second item behind the stuck one.
- **Re-push onto the branch that already exists for the issue.** Two branches for one issue is the failure the claim
  rule exists to prevent; name the remote branch and its sha in the instruction.
- **Withdraw the rest of its queue in writing.** A stuck bot handed twelve issues will keep starting new ones
  instead of finishing the first. Say which items are *parked, not deferred*, name who took the slice you moved, and
  promise to re-issue one at a time once the artifact exists — then keep that promise. The brief becomes: one task,
  the exact commands, report one line (the PR URL).

Pushing a third or fourth polite brief at a looping bot is the mistake: the artifact count has not changed, and the
queue grows while you rephrase.

## Your own rules are a repo artifact

A host agent's `SOUL.md` and skills live outside version control by default, so an instruction change is the one
behaviour change nobody reviews — and the host agents hold the write credentials. Any change to this skill or to the
planner's `SOUL.md` goes through an llgenie issue and a PR that commits the text under `agents/<profile>/` (issue
#791 is the tracking issue and the layout). File the issue first, dispatch the PR, then sync the profile from the
repository; never edit the live `SOUL.md` and stop there.

## Never prune: report worktrees instead

`make worktree-prune`, `git worktree prune` and `git worktree remove` are **owner-only**. The prune deletes
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

## Every count carries its limit

`gh issue list --json … --jq length` returns **30** because that is the endpoint's default page size, not because the
backlog shrank: measured 2026-10-28, the same repo read `30` with the default and **79** with `--limit 200`, while the
number had actually grown. Always pass `--limit` when counting (`--limit 200` for issues, `--limit 100` for PRs) and
say the limit next to the number, or the report invents a 35-issue cleanup that never happened.

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
- **Append to a workspace file, do not keep the fleet state in your head.** Write the run/claim/branch snapshot to a
  JSON file and diff it on the next pass: a bot that was quiet last pass and is still quiet is a finding.
