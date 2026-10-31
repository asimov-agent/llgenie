# Holds and closures: the two ends of the same defect

Load this whenever you audit `do-not-merge`, close out an issue, or apply a fleet rule change.

## A hold is a claim with a remedy, never a parking space

`do-not-merge` means *there is a concrete defect with a tracked fix* — never "this lane would rather not".

- **Placing it requires an issue.** The PR comment names the resolving issue, the exact condition for removal, and the lane that will remove the tag. No issue → no tag.
- **The flagging lane removes it**, quoting the sha or run id that proves the fix landed.
- **A bot-implemented PR is never held by default.** "I am not confident" is a review, not a label.
- **Audit every held PR each pass.** Tag + no linked issue = the tag comes off or an issue is filed in that same pass, and the owner is told which one you chose and why.

Why the issue is mandatory: `mergeStateStatus` reads `BLOCKED` for a live hold and for nobody-has-looked alike. The tag is the only place ownership lives, so it must carry the remedy — otherwise the PR parks until a human reads forty of them.

## Rule 14: announce the work where the work lives, and talk to the overlapping lane

A claim is a **comment on the issue or PR** — never a DM, never private memory. Before the first edit: post what you are taking, the branch, and what "done" means; then **re-read the thread**, because an existing claim, a live branch, or the last lane's note outranks the plan.

When two lanes share files, or one's change moves the other's premise: **message that lane** with the id, the sha and the need — then **post the conclusion in the issue**, since a decision living only in a DM does not exist for the next reader.

What it prevents, observed repeatedly: a head moving under a reviewer quoting a stale sha; a branch force-pushed back while a sweep was briefed on newer heads; two lanes calling the same PRs conflicting with neither knowing. Silence between two lanes on one set of files is how a green gets discarded twice.

Lane-shaped versions worth reusing: reviewer posts **sha + command + run id**; sweeper publishes `base sha · PR# · branch · head before → after` **before** the first push and skips a branch whose owner is mid-push; the merger comments its decision and its one-line decline reason per run; tester posts `run id · sha · n passed / n failed`; engine names the producer job and run id **before** waiting; docs asks for a written origin instead of reconstructing one.

## Rule 15: a fresh upstream base, and two comments that bracket the job

Before a worktree, branch or first edit: `git fetch upstream main` — canonical remote is `asimov-agent/llgenie`, so a fork named `origin` is not upstream — and branch from `origin/main` **at the sha fetched in that moment**. Never from a branch already held, never from a sha quoted in a chat message: the sha in a dispatch is stale by the time the lane reads it. The lane writes that sha into its **start comment**.

Every job is bookended: **start** (id, branch, main sha, what done means) and **finish** (head sha, what changed, the run id or command that proves it, what stays open). A start comment with no finish is an abandoned claim; a finish with no start has no baseline.

The lane reports both lines to the planner, and the **planner relays fleet state back** each pass — which PR is blocked on what, which premise moved, which lane owns which surface. That relay is the planner's half of the rule: a lane cannot see the board it is working on.

Why: one stale base produced three findings in a single rebase (ratchet baseline recorded 34/14 while main measured 107/151, `CHANGES.md` replaced by `docs/changes.d/`, a lint rule that did not exist at cut), and a verdict on a moved head had to be retracted after costing two lanes an hour.

## Rule 16: arm when done — and only on a `main` base

When the work on a PR is finished (last push, last check), **arm auto-merge and report the arm time** in the next comment. The trigger is *done*, not *approved*: arming is the handoff, and a finished-but-unarmed PR is invisible to every merger sweep. Arming is not merging — the merger still runs its own gates and still needs the review state.

Two exceptions, both stated with their reason so the absence is not read as neglect:

- a PR the owner forbade stays `auto=none (owner instruction)` with the instruction's location named;
- **a stacked PR — base is another open PR, not `main` — states `auto=none (stacked base: no required checks)` and arms on retarget.** On a non-default base `gh pr merge --auto` is not an arm: the branch has no required checks, so "auto" completes in seconds and merges the author's own work unreviewed into another lane's branch, dirtying the vehicle under a reviewer who already verified a head. A PR based on `main`, finished and green, is still armed; the carve-out exists only because the same command silently does something else there.

An **owner-applied label outranks a fleet default** — when the owner re-adds `do-not-merge` by hand after a lane argued it away, that is the deciding fact, not a stale hold to clean up. And **a merged PR never carries the tag**: a merged PR held by a label is noise, removed with a one-line reason.

## The other end: close what merged

An issue whose PR merged is closed **in the same pass**, with the merge sha and the run id that proves it. A merged PR with a live issue and a hold with no remedy are the same defect from opposite ends: tracked state that no longer means anything.

Same for a skill or SOUL change: when the rule lands, tick the referent — a rule recorded in one place and contradicted in another is a second source of truth, and two sources always disagree eventually.

## Applying a fleet-rule change (owner instruction)

1. **Amend the canonical block** in the rulebook issue and verify the text in the issue body (the gate compares block-in-soul, so the issue is the source).
2. **Message every lane** with the block verbatim plus **that lane's specific edge** — a lane obeys a rule it can map onto its own acts, and ignores one it cannot.
3. **Tell each lane to version it twice**: `agents/<profile>/SOUL.md` *and* the skill that governs the act (a PR skill for holds, a sweep skill for rebases). Then `make sync-agent-profile`, `CHECK=1` byte-identical, one armed non-draft PR. Never a private edit — the diff must exist in the repo.
4. **Dispatch the gate** that makes the rule executable, with a negative control (a held PR with no issue must *fail*).
5. **Audit the current boards** and name the PRs/issues that violate the new rule, so the rule has a first measurement rather than a promise.

## Pitfalls

- **A hold placed during an incident is not self-clearing.** The lane that set it moves on; nobody can tell whether it still means anything.
- **Two tools, one distinction.** *Request changes* = not right yet, no label, expires with the next review. `do-not-merge` = concrete defect **with an issue number**. If you cannot name the issue that fixes it, you are reviewing, not holding.
- **A conflict is the reason, not the remedy.** Either a rebase resolves it (do the rebase, no label) or the divergence is structural and needs the issue that removes the cause.
