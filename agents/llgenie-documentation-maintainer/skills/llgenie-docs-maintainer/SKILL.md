---
name: llgenie-docs-maintainer
description: "Use when auditing, filing or landing LLGenie docs changes."
version: 1.0.17
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llgenie, documentation, architecture-doc, pr-merge]
    related_skills: [llgenie-change-workflow, github, pr-finalization]
---

# Maintaining the LLGenie docs

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `llgenie-docs-maintainer`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## Role artifact (2026-11-01)

A doc gap is this lane's pull request, not an issue for `llgenie-issse-implementer`. Paths are `docs/**`, `agent-wiki/**`, `CHANGES.md`, and a doc-only refresh. Do not edit scripts, tests, or workflows. When the PR is up, `message_agent` to `llgenie-planner` with the PR number, the head sha, and what changed.

## When to Use

The work is `docs/**` (chiefly `docs/ARCHITECTURE.md`), `agent-wiki/**` or `CHANGES.md` on
`asimov-agent/llgenie`, or a PR whose change is documentation only.

Standing authority (the owner's grant, for the documentation lane): a documentation PR that is
**rebased onto the latest `main`**, carries **no documentation conflict**, has **no open finding**
against it, and is **green in CI**, is yours to land — **merge it yourself and remove the
`do-not-merge` label**, no approval and no waiting. Quote the grant in the merge comment. Every
other merge still waits for the user, and a PR you did not rebase or that still carries an open
finding is not covered by the grant.

## Reporting (fleet convention)

Every reply to the owner or to a teammate opens with one status line, then the detail:

```
BOT <profile> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>
```

**Timestamp every measurement, in the report itself** (`measured 18:4xZ: main=<sha> …`), and lead
with the sha and the verdict. The fleet relay delays messages by tens of minutes, so a row without a
timestamp is indistinguishable from a stale one and forces the reader to re-measure all of it — the
same defect as a census with no `measured at`. Sha-first plus a clock is what makes a delayed report
still actionable.

A report without an id or a branch is not a report. If the work was **not** dispatched to you — an
owner grant, a PR you already own — say that first; reporting "idle" while a PR of yours is in
flight is read by the fleet as a lane going quiet, and it invites a dispatch that collides with
your branch.

**A suspicious tool return is confirmed by one clean re-run, never reported as a degraded environment.**
An oversized batch of *dependent* commands sent as parallel calls comes back interleaved or blank, and
blank reads exactly like a broken tool. Re-issue the failed piece alone and act on that result; the
cause is almost always the batch (dependent steps must be serialized), not the environment. Sending a
teammate "tools degraded, work blocked" off the first odd return manufactures an alarm the lane then
has to retract — and a retraction costs more trust than the delay did. Diagnose, re-run, and report only
the state you re-read.

**A claim about what is pending includes draft state.** Before writing "blocked on approvals" or
"waiting on review", run `gh pr list --repo asimov-agent/llgenie --state open --json number,isDraft`:
a draft is invisible to the merge queue, to auto-merge and to a reviewer scanning for work, so a
queue description that omits one understates it — the same defect as a stale census, about work
instead of files.

**When a teammate quotes a number that contradicts yours, re-measure and date both.** In a fleet of
lanes reporting on a moving tree, a size, a count or a PR state in a message is a claim about the
moment it was taken, and it can be stale in *either* direction — a file that shrank after a dedupe
reads as a regression, a tree copy that is larger than live may be holding every rule twice. Run the
command again in this turn (`git show <sha>:<path> | wc -c`, `git ls-tree`, `gh pr view --json
state,mergedAt`), answer with that output *and* the moment the other figure was true ("that was before
the sync"), and never carry a number you did not just re-read into the next claim. Arguing which
number is right wastes a turn; dating them ends it.

## Standing authority and where it is versioned

The merge grant for documentation PRs, and the fleet's seven standing rules from 2026-10-28, are
repository artifacts: `agents/llgenie-documentation-maintainer/SOUL.md` on `asimov-agent/llgenie`
(issue #873, per #791). Change behaviour there by issue + PR, never by editing only the local
profile — a private edit cannot be diffed, and the local `SOUL.md` is a copy. `agents/manifest.json`
lists the profile with `rules: ["never-implement"]`; this lane deliberately does not declare
`never-merge`, because it holds the narrow grant to land documentation-only PRs, and a manifest that
claimed otherwise would make the file lie. `references/agents-soul-tree.md` has the mechanics:
extracting the canonical block and asserting it verbatim, why the fenced block must be diffed against
the issue's numbered list before it is trusted, the `live-longer` refusal `make sync-agent-profile`
raises and how to settle it deliberately, what the manifest's rule check actually matches, and why
such a PR must never land before the tree it is stacked on, and the recipe for versioning a lane's live-only skill bundle with its byte-compare proof.

## Host behaviour vs the versioned tree (ongoing issues and docs PRs)

`agents/<profile>/SOUL.md` and `agents/<profile>/skills/**` on `main` are the **versioned** copy; each
`llgenie` bot's **live** profile under `~/.hermes/profiles/<profile>/` is what actually runs. They drift:
a lane edits its live SOUL/skill and nothing watches the repo copy. So **every ongoing issue and every
docs PR whose subject is (or cites) a SOUL/skill must be checked against the live host profile**, not
assumed true from the repo copy alone — the host is where the behaviour actually executes, so a gap
between `agents/**` and `~/.hermes/profiles/**` is a finding, and a **new issue** is filed for it.
The step-by-step runbook — the triggers, the two commands, the delta-record table the PR/issue body
must carry, and the new-issue routing — is the sibling reference `references/live-vs-tree-drift.md`;
load it before a SOUL/skill review so the captured delta is the reproducible one, not a prose guess.

The lane's docs-freshness ownership — README + `docs/` are this lane's against the tree, the 30-min
change monitor that answers "does any user-facing doc/README need an update?" before other work, and
the never-a-private-edit rule — is `references/docs-freshness.md` (versioned via #1239).

Concretely, treat this as part of comparing the behaviour of existing issues and their implementations:

- `make check-agent-profiles` names the gaps: `live-longer`, `live-edited-not-tree`, `fleet-block-drift`
  (the last is tree-only and reds CI; the first two need a live profile, so CI never sees them).
- `make sync-agent-profile PROFILE=<p> CHECK=1` byte-compares the tree copy to live — exit 0 means the
  pair is identical, a `differ` line names the first divergent file. **Run it from the branch's own
  worktree, never the main checkout or a stale local `main`:** it reads the tree at the cwd, so a CHECK
  launched elsewhere compares live against *that* tree — a red it reports then belongs to whatever is
  checked out there (usually another lane's live-only skill), not to the branch you are versioning.
  A red you cannot reproduce from the branch worktree is the wrong-cwd signal, not a fleet finding.
- **Direction is judged on content, per hunk, never copied blindly:** a tree copy that is a *prefix* of
  live means live is newer — re-take live→tree; a live file edited *after* the tree commit means the
  lane's behaviour outran the repo — commit it via an issue+PR under `agents/<profile>/`.
- **Never run `sync-agent-profile` in write mode for a lane whose live is richer** — it truncates and no
  gate notices (#791). `CHECK=1` only.
- **Your own `skill_manage` patch to this lane's skill edits LIVE only, so it opens tree drift the moment
  it lands.** The skill-write tools write the host profile; the versioned copy under
  `agents/<profile>/skills/**` does not move with them. After any self-improvement pass, either fold it
  live→tree in that same session (issue → branch → byte-identical copy → `CHECK=1` → PR) or record the
  byte delta and file the fold on the next pass — an unfiled drift is precisely the host-vs-repo gap this
  lane exists to close. **A "reload your SOUL and skills" instruction is the cheapest drift check the
  lane gets:** after re-reading, `cmp` the live skill against the tree copy and treat any size gap as a
  finding (new issue + fold PR), because live is what runs and the tree is what a reader trusts — a live
  file that grew by one lesson is a tree that is silently wrong by that lesson.
- **Re-copy live→tree at PR time, not when you cut the branch.** A versioning PR stays open while the
  lane keeps editing its live skill, so a tree copy committed early is already stale by merge (live
  gained lessons twice during one PR) and `sync-agent-profile CHECK=1` then reds on `main` against
  the newer live. Re-run the live→tree copy and `CHECK=1` at the final head before pushing/landing;
  if a held branch's snapshot is behind, re-copy — do not ship the stale snapshot. **For a multi-file sync, `cmp` every live file against its committed tree copy AFTER the commit and before the push** — live is written while you work, so a copy that was byte-identical minutes ago can drift before the commit; amend the re-copy at that head rather than discovering the drift on `main` after landing. Record the per-file byte counts (tree@base → head==live) in the PR body so a reviewer can re-run `cmp`.
- A gap found while reviewing someone else's PR is a **new issue**, scoped to the owning lane, with the
  delta (profile, file, class, tree/live bytes, direction) recorded in the issue and PR body per
  `references/live-vs-tree-drift.md`; a gap that lives only in a comment is not trackable and gets one.
  The docs lane writes the fix only under explicit dispatch (name the delegation in the PR body — e.g.
  #1062 to the planner, #885 to the rebase lane).

## Fixing a measured defect (issue first)

A defect the audit measures is a change, and this repo's contract is issue → branch → PR that closes
it. Do not push a doc fix straight to a branch of your own:

1. `gh issue create` with the six sections in this order — `## Problem` (measured, with a table),
   `## Why it matters`, `## How we fix it`, `## Benefit`, `## Acceptance criteria` (one `- [ ]` per
   provable outcome), `## Technical` (files, commands, numbers). Verify the order after filing by
   reading the body back with `gh issue view <n> --json body` and comparing headings in code;
   `scripts/check_issue_body.py` only takes `check`/`report` and reads the repo's producers, it has no
   `--body-file` switch, so it cannot validate a single filed issue.
2. Branch from `origin/main` in a **new** worktree, fix the doc, and put `Closes #<n>` in the PR body.
3. Every number in the issue body and the PR body is a command output you just ran, with the base sha
   beside it — a reader must be able to re-run it and get the same count.

## Holds, and the other half of every claim

**Never place `do-not-merge` without a remedy** (issue #948, rule 13 of #873). The label means "a concrete defect, and here is the issue that fixes it" — never "this lane would rather not" and never "until a human looks". If you place one: file the issue, name its number and the exact removal condition in a PR
comment (`#<n> lands`, `the census matches at <sha>`), and remove it yourself when that lands, quoting
the sha or run id that proves it. A PR a bot implemented is never held by default. A hold whose
reason expired reads exactly like an abandoned PR — `mergeStateStatus` is `BLOCKED` either way — so
before describing a PR as "blocked on approvals", run
`make auto-merge-explain PR=<n> REPO=asimov-agent/llgenie` and say which of label / review / pending
check is blocking.

**A document may not report a state it did not re-read.** This lane's own species of that defect:
"six profiles" while the tree held seven, "cross-repo therefore unapprovable" when the permission was
`admin`, a board described as "blocked on approvals" while three drafts sat unmentioned. Re-read the
thing the sentence is about — the tree, the ACL, `gh pr list --json isDraft`, the queue — and name the
command that read it. A count taken before a merge is a claim about a branch that no longer exists.

**A decision with no written origin is asked for, never reconstructed** (rule 14 of #873). This lane
reads the trail for a living, so the trail is its input: a rule, a hold or a settlement that exists
only in a DM or in someone's memory cannot be documented, only guessed — and a guess in `docs/`
becomes fact for the next operator. When the written origin is missing, comment on the issue asking
the lane to post it, and say in the PR body that the rule has no written source yet. The same shape
keeps `docs/changes.d/` honest: an entry per *decision*, not per commit.

**Start from a freshly fetched `main`, and bookend the work** (rule 15 of #873). `git fetch origin main`
in the moment before cutting the worktree, branch from the sha that fetch returned, and write it into
the first comment on the issue/PR — never branch from a branch you already had and never from a sha
quoted in a chat message, which is stale by the time it is read. Close with a finish comment: head
sha, what changed, the run id or command that proves the numbers. **Post the finish bookend as its OWN
comment AFTER the last push/amend** — a single comment that tries to be both start and finish is
invalidated by the very next amend (the head sha it names no longer exists), so the finish one is
written last; if an amend or re-render moves the head after you posted it, post the finish bookend
again naming the new head rather than leaving a comment that cites a superseded sha. In this lane the rule lands in the
artifact itself: **a document states the sha its claims were measured at**, so a reader can tell
whether it describes `main` or a PR — a census whose sha is not written down is a claim about a branch
that may no longer exist.

**Arm auto-merge when the work is done, not when it is approved** (owner directive). The last push and
the last check finish the work: `gh pr merge <n> --squash --auto` immediately, then report
`auto=armed <hh:mmZ>` in the next comment. A finished, unarmed PR is invisible to every merger sweep.
Exceptions, both reported rather than assumed: an owner-forbidden PR (`auto=none (owner instruction)`
plus where the instruction lives), and a **stacked** PR — arming it lands it into its base, so say
which base it merges into instead of implying it lands on `main`.

**Arming works while the PR still reads `BLOCKED`.** `gh pr merge <n> --squash --auto` is accepted with
`mergeStateStatus: BLOCKED` and `REVIEW_REQUIRED`; it records the intent and GitHub merges the moment
the review/check requirements clear. Read it back from the **REST** endpoint and quote `enabled_at` in
the report, because "I armed it" without the timestamp is the same unverifiable claim as "CI looks
green":

```bash
gh api repos/asimov-agent/llgenie/pulls/<n> --jq '.auto_merge | {enabled_at,enabled_by,merge_method}'
```

**GraphQL `gh pr view --json autoMergeRequest.enabledAt` is NOT authoritative — it can print a non-null
`enabledAt` while REST `auto_merge.enabled_at` is `null`, i.e. the PR is NOT armed.** A phantom
`enabledAt` (a leftover timestamp from an earlier arm attempt, surfaced by the GraphQL cache) reads
exactly like a successful arm and produces a wrong "armed" claim that a teammate then has to correct.
When the two disagree, **REST wins**: `gh pr merge <n> --squash --auto` exits 0 even when it arms
nothing under the #964 failure mode, so the exit code is not the fact — read `auto_merge.enabled_at`
back, and re-arm if it is still `null`. Before calling a null a silent no-op, check `state` (a fully
approved, green PR can merge instantly and then show a null pending request — see the paragraph below).

**The arm read-back proves itself by `enabledAt`+`enabledBy`+`mergeMethod`, NEVER a field called `enabled`.**
GitHub's GraphQL `PullRequest.autoMergeRequest` object exposes only `enabledAt`, `enabledBy` and
`mergeMethod` — there is NO boolean `enabled` field, so a teammate who queries `.autoMergeRequest.enabled`
gets `null`, reads it as `FALSE`, and flags a perfectly armed PR under the #964 failure mode. When a
teammate reports "autoMergeRequest shows enabled:FALSE", do not re-theorize — pull the FULL object
(`gh pr view <n> --repo <r> --json autoMergeRequest --jq '.autoMergeRequest'`) and quote it. An
`enabledAt` that is non-null, an `enabledBy` set to the enabling actor (here the PR owner `andyholst`)
and `mergeMethod: SQUASH` IS the armed state; a null `authorEmail`/`commitBody`/`commitHeadline` is just
"no merge-commit overrides set", not a disarmed flag. Re-running `gh pr merge <n> --squash --auto` is
idempotent and removes all doubt — do it, read the full object back, and answer with the JSON, not an
argument about which field is real.

**A NULL `autoMergeRequest` read-back is NOT proof the arm no-op'd — read `state` first, because the merge
may have ALREADY COMPLETED.** When the PR is `APPROVED` and fully green at the moment you arm, GitHub fires
auto-merge immediately: the merge lands before your read-back and `autoMergeRequest` then returns `null`
(no *pending* request) — which looks identical to the #964 silent failure but is a success. Before calling
it a failed arm, run `gh pr view <n> --repo <r> --json state,mergeCommit,mergedAt`: `state=MERGED` plus a
real `mergeCommit.oid` plus a `mergedAt` at/near your arm timestamp means the arm worked by landing
instantly. Only diagnose the #964 silent no-op (base not the default branch, nothing armed) when the PR is
still `OPEN` with a null object; and even then, `mergeStateStatus: UNKNOWN` right after an arm is the
tell that the merge-ref is being re-evaluated — re-read `state` and `mergeStateStatus` a moment later
before reverting to "nothing armed". **A `mergeable_state` that stays `unknown` for many minutes on an
all-green head is the other shape — check `state`/`mergedAt` FIRST: the owner may have merged the PR
directly, and the persistent `unknown` is GitHub resolving a merge that has already landed.** Polling
`mergeable_state` as an arm gate on a PR whose `state=MERGED` is a claim about a branch that no longer
exists, and no `enabled_at` read-back will ever arrive for a PR that merged — a `--auto` request against
such a PR is parked-then-satisfied. Drop it, kill any watcher still polling it, and report the merge sha,
not an armed-read-back that cannot come. (Measured 2026-11-01: #1254, head `35a8ff52` all-CI SUCCESS,
`mergeable_state` `unknown` 00:18→00:28Z, then found already merged `22b817af` — the owner merged at
00:16:07Z while the `unknown` was still recomputing.)

## Idle / empty-queue audit (continuous improvement, #1245)

When this lane's reactive queue is empty for N=2 consecutive passes (no dispatched work, no in-flight
gate it owns), run one bounded own-domain audit. For this lane: **main-versus-docs alignment** (README
and skill sections stale vs current `main`), **skill-freshness** (a skill 2+ releases old — read the
`version:` frontmatter against the release ledger in `CHANGES.md`), and **change-note coverage** (a
behavioural surface with no `agent-wiki/` note + `docs/changes.d/` row, the #1123 change→note gate).
Every finding is filed as a refined six-section issue tagged `agent:implement`, routed through the
normal queue — never implemented by the same pass; otherwise record "re-audited at `<sha>`, no
findings". One-pass scope, no infinite loop; never overrides real reactive work.

**Run the audit in a fresh scratch worktree at `refs/remotes/origin/main`, never the repo's
main checkout.** That checkout usually sits on a local `main` branch many merges behind the remote
tip, so `make check-docs` / `docs_audit.py` run there measure an OLD tree and report the census
referent as "no usable referent" plus lower agent-wiki/tracked counts — figures that read as defects
but describe a branch that no longer exists. `git fetch origin refs/heads/main:refs/remotes/origin/main;
git worktree add /tmp/aud refs/remotes/origin/main`, run the gates there, `git worktree remove`
after; name the fetched sha in the record. **Prove change-note coverage with `make -s check-docs`
(green = every note has a fragment row AND the change→note gate passes), not by globbing
`docs/changes.d/*<pr-number>*`** — fragments are named by note stem or issue, never the PR number,
so a PR-number glob returns 0 and reads as a missing note that is not missing; trust the gate over
the glob.

## Landing a docs PR (the loop that works)

1. Work in the PR's own worktree. `git worktree list` names it (`…/llgenie-wt/pr<N>`); never
   `git switch` in the user's checkout — it usually carries an unrelated modified file.
2. `git fetch origin --prune`, then `git rebase origin/main` in that worktree. Doc refreshes are
   cut on a 6-hour cadence, so `main` has almost always moved: the base the doc was *generated*
   at is not the base it lands on.
3. **Re-measure every factual claim against the rebased tree, in code — after *every* rebase, not
   once.** A bot-generated doc is a census, and a census that lags its base by one merge is the
   exact defect reviewers block on; a refresh that has already been rebased once is the common
   case, so treat the numbers as stale by default and recompute them. `scripts/docs_audit.py`
   (this skill) does the whole sweep read-only in one pass — census vs the doc's claims,
   `scripts/*.py` the doc never names, `make` targets that do not exist, and the
   workflow/schedule claims in `docs/BOTS.md`:

   ```bash
   python3 ~/.hermes/profiles/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/scripts/docs_audit.py
   ```
   Patch the numbers where they differ. Leave every non-census sentence alone unless it is
   provably wrong at this head. Quote the base sha the numbers describe in the PR body — the
   body's "at `<sha>`" line is the claim a reviewer checks first. A `measured at <sha>` clause added
   to the document itself belongs in the **generator's template** (`scripts/architecture_bot.py`), not
   hand-written into the page: `docs/ARCHITECTURE.md` is regenerated wholesale on a six-hour cron, so a
   hand-added provenance line is deleted by the next run and any gate that asserts it reds on a doc
   nobody edited.
4. Sweep the doc for surfaces that landed *after* the refresh was generated — every `scripts/*.py`
   and every gate should be named somewhere in `docs/ARCHITECTURE.md` (the audit script lists the
   gaps). A deprecated alias (the retired serve script) and a helper the doc deliberately omits may stay
   out; say which and why in the PR body so the omission reads as a decision. Nothing enters the doc
   unless it exists at the head it describes: `git merge-base --is-ancestor <commit> HEAD` for a
   commit, `git ls-tree -r --name-only HEAD -- <path>` for a path, `grep -n '^<target>:' Makefile`
   for a target. And when a workflow's job set, trigger or filter changes, the doc row that describes
   it changes in the **same** PR — a doc that lags a workflow is read as verified, which is worse
   than no doc.
5. Gates, cheapest first: `make -s lint check-docs check-wiring check-pr-authors check-issue-bodies
   check-pr-hygiene check-workflows check-dispatch-forms`. `check-docs` also prints the
   user-facing target count and the `agent-wiki/` entry count — the latter is a free cross-check
   of the census.
6. Commit as `Asimov Agent <support@docondee.com>` (`git -c user.name=… -c user.email=… commit`),
   no `Co-authored-by:` trailer, then `python3 scripts/check_pr_authors.py check --base origin/main --head HEAD`.
7. `git push origin HEAD:<branch>`. After a rebase the push is refused ("tip is behind its remote
   counterpart"): prove the rebase changed nothing but the base first —
   `git range-diff <old-base>..<old-head> origin/main..HEAD` must show `=` on every replayed
   commit — then force-push under a lease. **The lease expects a literal SHA, not a ref path:**
   `--force-with-lease=<branch>:refs/heads/<branch>` is rejected with `! [rejected] … (stale info)`
   because the expected value is compared as a sha and a ref path never matches. Either form works:
   `git fetch origin +refs/heads/<branch>:refs/remotes/origin/<branch>` and then plain
   `git push --force-with-lease origin HEAD:refs/heads/<branch>` (the remote-tracking ref you just
   fetched becomes the expectation), or `--force-with-lease=<branch>:<literal-old-sha>`. Fetch
   immediately before either: the lease protects against a stranger's push, not against your own
   stale memory of where the branch was.
8. Update the PR body (`gh pr edit --body-file`, then **read it back** and grep for the new head
   and `closes #<n>`) — **after the last push, never before.** A body that names a "final head" sha
   is invalidated by the very next commit, so any further push (a re-copy, a rebase, a lint fix)
   re-opens the edit step; write the head line last or it lies. **The head can move without a push of
   yours** — a rebase lane, the reviewer, or an automation rebases the branch under you, so "my last
   push" is not the head. Before reading a PR's state or refreshing its body, re-derive it from the API
   (`gh pr view <n> --json headRefOid,baseRefName`) and, if it differs from the sha the body names,
   treat the body as stale and refresh it: a body naming a pre-rebase base or head is a live defect that
   reads as fact, exactly like a census with no `measured at`. If another open PR edits the same doc, name it in the body and state the
   ordering: whichever lands second re-measures the census at the new base, and that re-measure is
   the second landing, not a defect to prevent.
9. **Try the merge before any approval — but you cannot supply the approval yourself.** `gh pr merge
   --squash --match-head-commit <sha>` is the smaller action; this repo carries no classic branch
   protection, so a `REVIEW_REQUIRED` decision sometimes does not block the merge. When it does, note
   the identities: the PR *author* is `andyholst` (the push token) and approvals come from the separate
   `asimov-agent` identity, so `gh pr review --approve` from your lane is the owner approving the
   owner's own PR — invalid. Route the `asimov-agent` approval to the owner/planner, and hand the PR to
   the reviewer lane for the review itself (its SOUL forbids it from approving). Arming alone will not
   merge a ruleset-pinned `REVIEW_REQUIRED`.
10. In the merge comment, quote the authority you acted under — the owner's words, when they said
    it, and the narrowed form a reviewer recorded — so a reader a month later sees who authorised
    the merge rather than a bot's initiative. Then confirm the label is gone and the linked issue
    actually closed (`gh issue view <n> --json state`): `closes #<n>` in a body that never landed
    closes nothing.

## A shared index file is a conflict point — one row per file

`CHANGES.md` was one table every PR prepended a row to; at `main@97a24063` 10 of 12 open `DIRTY`
PRs conflicted on it alone (issue #934). The durable shape is **one index row per file**:
`docs/changes.d/<note-stem>.md` holds exactly one row, and `CHANGES.md` is rendered from the
fragments by `make changes-index` (`scripts/changes_index.py`). Rules that follow:

- A change PR adds `agent-wiki/<stem>.md` and `docs/changes.d/<stem>.md` and **never** edits
  `CHANGES.md`. Do not gate `CHANGES.md` currency — requiring it per PR re-creates the append point.
  `make changes-index-report` prints how far behind it is.
- **The docs lane's OWN versioning/doc PR is the exception that renders it — and the render is the
  currency job, done IN that PR, not deferred.** After the note+fragment are written and the
  functional commit is in, run `make changes-index` (it writes from every fragment in
  `docs/changes.d/`), then amend the commit and re-push. Expect the diff to include **other lanes'**
  unrendered rows alongside yours (the render is global, not per-PR) — that is correct and minimal
  (your row + whatever note landed without a render), not scope creep; quote the added rows in the
  PR body. `check-changes` is **not** a `make` target — it is a check function run *inside*
  `check-docs`, so never `make check-changes` (it 404s); the proof the render is consistent with the
  fragments is `make -s check-docs` staying green ("CHANGES.md links no missing note").
- Keep the gate falsifiable in both directions: note with no row → red, row whose note is gone →
  red, malformed row → red. Deriving rows purely from note frontmatter loses the dangling case.
- **A rule is only enforced where a gate checks BOTH directions — a one-directional gate is the
  blind spot.** The change-record rule was gated note→fragment (a note must have a row) but never
  change→note, so a behavioural change with no `agent-wiki/` note merged green (measured: roughly a
  third of recent merged PRs touching `scripts/`, `agents/` or `docs/` carried no note). When you
  add or review a gate, name the direction it is silent on and close it: a change owes a note when
  it touches a behavioural surface (`scripts/**`, `agents/*/SOUL.md`, `agents/*/skills/**`,
  `agents/manifest.json`, `docs/**/*.md`, `.github/workflows/**`, `Makefile`, `data/**`,
  `containers/**`, `openspec/**`), while `tests/**`, `agent-wiki/**`, `docs/changes.d/**` and
  `CHANGES.md` are exempt. A live→tree skill sync is such a change even though it only copies
  bytes the live profile already ran — it *edits* `agents/*/skills/**`, so it owes its own note;
  ship the note in the same PR as the sync, not as a follow-up, or the gate reds the sync the
  moment the gate PR merges. Assert the surface set **additively** — a behaviour/subset check, never a
  pinned file list — or the gate reds on the next legitimate surface and gets edited to match the
  code. Prove both lines: a no-note behavioural change fails, an exempt change passes.
- Prove the property structurally, not by assertion: two scratch branches each adding a note +
  fragment, then `git merge-tree --write-tree a b` must print a single tree sha and no conflicted
  path.
- Migrating existing rows: split them **verbatim** into fragments, then `make changes-index`; diff
  the data rows against `git show HEAD:CHANGES.md` so the refactor provably rewrites nothing.
- `AGENTS.md` is a **protected** file in this environment — a write is refused without an approval
  prompt, and retrying another way is forbidden. When a change makes a rule in `AGENTS.md` stale,
  file the wording update as its own issue, link it from the PR's `Not covered`, and say so in the
  body rather than shipping a rulebook that contradicts the gate.
- The OpenSpec CLI runs as root in its container: `make openspec-new` leaves the new change dir
  root-owned, so `write_file` fails with `Permission denied`. Fix it without sudo by
  `docker run --rm -v "$PWD":/repo alpine chown -R "$(id -u):$(id -g)" /repo/openspec/changes/<name>`.
- In this checkout `origin` is the upstream (`asimov-agent/llgenie`) and `fork` is `andyholst/llgenie` — check `git remote -v` before pushing. A new branch and PR can be created on `origin` (`gh pr create --head <branch>`); only an **existing** PR whose head sits on the fork needs `git push fork` (read `headRepositoryOwner` first).

## Pitfalls

- **A force-push RESETS CI on the new head — every check re-pends, `mergeStateStatus` returns `BLOCKED`, and the arm gate REOPENS; never treat a prior head's greens as inherited, and make the arm mechanical with an executing arm-on-green watcher.** The fold/rebase that fixes a PR lands as a new head, and GitHub starts a fresh run set for it (`gh pr checks` shows all `pending`, then fills back in); an arm earned at the old head does not carry to the new one. Because the long-pole `linux / unit` then re-runs in full (~1h45), do not burn a foreground poll on it — a foreground arm loop is clamped (~7 min) and can never span the job, so it always ends on `pending=1` and looks like a stall. Instead run a **background arm-on-green watcher that performs the mutation itself**: poll `gh pr checks <n>` until `pending=0` and `fail=0` with a `pass` present, then `gh pr merge <n> --squash --auto`, read REST `auto_merge.enabled_at` back, post the read-back on the PR, and `notify` on a sentinel (e.g. `ARM_DONE_<n>`). A notify-only watcher defers the arm to a turn that may never come; the executing watcher puts the arm on the critical path. Kill the notify-only watcher before starting the executing one so two loops do not double-post, and keep the watcher machine-guarded (`pending=0 fail=0 pass`) so it never arms on an in-progress unit. **The window between a force-push's old-head checks draining and the new head's checks reporting can read `pending=0` with NO `pass` line** — that empty window is exactly why the guard requires a `pass` present; the watcher must not arm there, and after such a window read REST `auto_merge.enabled_at` to confirm it is still `null` (nothing armed against the now-void old head) before trusting the next green.
- **A `message_agent` return of `status: ambiguous` with `queue_full` and "Do not resend" is NOT a lost report — the on-record comment is the durable channel.** When a DM delivery cannot be confirmed, do not resend it into the same full queue; the same content lives on the issue/PR thread (the record a stranger can find), and you re-notify the teammate at the next milestone (the arm read-back, the finish bookend). Treat the DM as best-effort and the thread comment as authoritative.
- **A `success` on the WRONG run at the right head is as misleading as a `cancelled` sibling — resolve the run id from `gh pr checks`, never guess it.** Some pushes spawn several runs at one sha (a `guard`/`holds`-only quick run plus the full matrix). A watcher polling the quick one sees `completed/success` within minutes and a report then calls the head green while the real matrix's `linux / unit` has not concluded. Before arming any watcher, read `gh pr checks <n> --repo asimov-agent/llgenie`, which prints each job's own `actions/runs/<id>`, and pick the id that carries `linux / unit`; poll that run's jobs (not just `.status`) and report the unit job's own conclusion. `gh run list --commit <sha>` alone does not tell you which duplicate is the matrix.
- **Heartbeat-coalesced watcher output can quote a stale head — re-read the PR directly before acting on a poll line.** A 5-minute poll loop's lines can arrive batched and show `headRefOid` from before your force-push plus a transient `DIRTY`, contradicting a measured `MERGEABLE` at the new head. Treat any poll line older than the moment of a push as history: run `gh pr view <n> --json headRefOid,mergeable,mergeStateStatus` now, timestamp it, and only then decide whether a rebase is needed (a `DIRTY` that survives the direct read after `git fetch origin refs/heads/main:refs/remotes/origin/main` is real).
- **`gh pr checks` lags the push by a minute and then lies.** Right after a push it prints
  `no checks reported on the '<branch>' branch`; the run exists. Use
  `gh run list --repo … --commit <sha> --json databaseId,status,event` and poll
  `gh run view <id> --json status,conclusion,jobs` instead. Jobs can sit `queued` for minutes on
  a starved runner — that is not a red check. To wait on a long run, start
  `gh run watch <id> --interval 60 --exit-status` in the **background** and let its completion wake
  you; a foreground `sleep`/poll loop is clamped (~3 min) and dies mid-wait, which reads like the
  run failed when nothing happened. **If you hand-roll the poll, format the `jq` flat —
  `.status + "/" + (.conclusion // "")` — and check the first poll prints a NON-EMPTY status before
  trusting the loop.** A nested-escaped form (`"\(.status)/\(.conclusion//\"\")"`) fails `jq`
  parsing, so `$A`/`$B` are empty and a `case "$A $B" in *completed*)` guard never matches: the
  watcher spins forever with no status and no `FINAL_*` wake — it looks healthy and silently never
  reports the job finishing. `gh run watch` avoids the whole class; prefer it over a bespoke loop.
- **`REVIEW_REQUIRED` is not something your lane can clear — the author and the approver are different identities.** The PR *author* is `andyholst` (the push token); approvals come from the separate `asimov-agent` identity. So `gh pr review --approve` from your lane is the owner approving the owner's own PR (invalid), and the reviewer lane will not approve either (its SOUL forbids grading the code it could fix). Where a ruleset pins `REVIEW_REQUIRED`, only an `asimov-agent` approval (owner, or the planner acting under it) unlocks it — arming alone will not merge. Read `gh pr view --json reviewDecision,mergeStateStatus,author` before calling it blocked, and route the approval rather than self-approving.
- **`main` has no classic branch protection** (`/branches/main/protection` 404s; rulesets own it).
  So `mergeStateStatus: BLOCKED` is always the review decision, a pending check, or the label —
  `make auto-merge-explain PR=<n> REPO=asimov-agent/llgenie` names which.
- **The `do-not-merge` label is a teammate's hold, so the grant must be on record for THAT PR.**
  The reviewer who placed it (and who may dismiss an approval) treats an agent clearing it as an
  agent merging the owner's repo, and will re-apply it. Do not settle that by acting twice: state
  the owner's grant, ask the owner to confirm it for this PR in writing, then approve → clear →
  merge and say which grant you are acting on. Never merge on the strength of a general mandate.
- **Before any `gh run rerun` or `gh run cancel`, read the PR's state.** `gh pr view <n> --json
  state,mergedAt,headRefOid` first. Once the PR is `MERGED`, its run is *history, not work*: the head
  that run belongs to is no longer the PR's head, so a rerun cannot produce a verdict anyone can use
  and a green result would attach to a stale sha. Check before diagnosing a stall and again before
  acting — a merge can land while you are waiting on a slow job.
- **A merge event is not proof its gates went green — verify the head's check-runs before ever
  reporting "CI green at the merge".** An owner/planner gate (or a relayed "it evidently completed
  green") can merge a PR while the deciding leg — the long `linux / unit` — is still `in_progress`,
  because the merge gate is their intent, not the run's conclusion. When asked to verify a fold / a
  doc PR "green at the merge", read the *head sha's* checks directly, never the merge fact or a
  chat claim: `gh api "repos/<r>/commits/<head>/check-runs?per_page=100" --jq '.check_runs[]|{name,status,conclusion}'`
  (cross-check the matrix run with `gh api repos/<r>/actions/runs/<id> --jq '{status,conclusion}'`).
  A `status: in_progress` / `conclusion: null` on the deciding job means it **never completed** — say
  "merged through a pending deciding leg" and correct any teammate premise that called it green. Two
  disciplines stay separate: your arm watcher's `pending=0 fail=0 pass` guard protects *your* side
  (and a merge that already happened is not evidence your guard was ever satisfied — kill the moot
  watcher and report the merge sha plus the true check state, not an `enabled_at` read-back that
  cannot come).
- **A cancelled run is not a failed run — check for supersession before diagnosing.** A fleet sweep
  (an owner instruction to pause the bots and cancel runs) cancels in-flight runs repo-wide, and the
  run then reports `cancelled` with its remaining jobs `cancelled` at scattered timestamps while the
  earlier ones are green. Before concluding anything:
  `gh api repos/<repo>/actions/runs/<id> --jq '{attempt:.run_attempt,status,conclusion}'` and
  `gh api "repos/<repo>/actions/runs?head_sha=<sha>"`. One run and no new head means nothing
  superseded it, so recover with `gh run rerun <id>` at the **same** head. Never push an empty commit
  to manufacture a fresh run: it moves the head and voids a grant pinned to a sha. **A cancelled
  upstream job also makes the downstream jobs `skipped`, and `skipped` is not a pass:** a cancelled
  `scope`/gateway step means the matrix never received its job list, so `linux/unit: skipped` proves
  nothing ran — count  the `success` jobs and confirm the specific gate has a real conclusion before
  calling a head green, and never report `failed=0` as "verified" while checks are `skipped`/`cancelled`.
  **A duplicate run at the same head is the other face of this:** `gh pr checks` renders a job from
  *any* run at that sha, so a `cancelled` duplicate can read as `fail` while a sibling run at the
  SAME head is `success`. Run `gh run list --branch <b> --json databaseId,headSha,status,conclusion`;
  if a sibling at the head is `success` and the reported job is `cancelled`, `gh run rerun
  <cancelled-run-id> --failed` at that same head — **never push** — then confirm the gate has a real
  conclusion in a completed run before calling it green or red. Two identical cancellations
  (`Timeout (0:05:00)!` xN in `make ci-unit`, siblings green) mean a starved runner, not your diff:
  stop rerun-looping and wait for a quiet window — the fingerprint is in
  `references/ci-triage-for-docs-prs.md`.
- **`closingIssuesReferences` is eventually-consistent — a `none` right after a PR is created is not evidence the `Closes #<n>` keyword failed.** The field is populated asynchronously, so `gh pr view --json closingIssuesReferences` returns empty for minutes after creation; do **not** edit the body in response. Re-read later, or confirm the link from the body text and the issue's own timeline. A positive is proof; a negative is only "not yet, or genuinely absent".
- **A local full `make test-unit` pass is evidence, not the CI verdict.** CI runs with a clean HOME where live-vs-tree profile comparison is skipped, so a test that reads the host profile can pass locally for a different reason than CI runs it (or vice versa).  Report a local suite as evidence — its exit code and the head sha — and still wait for the CI job's own conclusion before calling a head green; the two can disagree, and the CI one is the one that gates.
- **Verify at the exact STATE the acceptance criterion names — a weaker proxy does not satisfy it.** When an
  issue's `## Acceptance criteria` says "green on a clean merge-tree of `origin/main`" (or "on every PR
  rebased onto it", or "under the gate PR's version"), a green on your branch head — locally and in CI —
  is a *different* measurement, and the integrity check treats it as not passed. Reproduce the named
  state and run the gate there, in code:  `git fetch origin +refs/heads/main:refs/remotes/origin/main`,
  `git worktree add /tmp/mt <origin/main>`, `git merge --no-ff --no-commit refs/remotes/origin/<branch>`,
  then `make -s check-architecture-census` and `make -s check-docs` on that merged tree. **A PR head that
  lives only at `refs/pull/<n>/head` (a fork head, or a branch ref that was never fetched) cannot be
  merged directly** — `git merge refs/pull/<n>/head` fails `not something we can merge` because that ref
  is not in the worktree's ref namespace. Fetch it to a named remote-tracking ref first:
  `git fetch origin +refs/pull/<n>/head:refs/remotes/origin/pr<n>`, then `git merge refs/remotes/origin/pr<n>`. — a conflict-free
  merge plus `[census-gate] OK … referent … is an ancestor of HEAD` is the proof the criterion asks for,
  and it also proves the change cannot conflict on landing. Run the subtle-but-required variant too when
  the criterion names it (e.g. the gate PR's own checker via its head blob). Remove the scratch worktree
  after (`git worktree remove /tmp/mt --force`); it is your own verification artifact, not a lane's.
- **Your own versioned `SKILL.md`/`SOUL.md` is scanned by the suite — a retired symbol in it reds CI,
  and it is the file you least expect.** A live skill that still names the retired underscore module/CLI
  that `scripts/module_name_guard.py` forbids (the pre-rename spelling replaced by `llgenie_serve`) fails
  `test_rename_llgenie_serve` and spends a full ~1 h matrix — and the lesson's own text must not spell
  the token it warns about, or it trips the very guard it describes. Before pushing a SOUL/skill sync,
  grep the versioned copy for every retired identifier (`grep -rn '<old-name>' agents/<profile>/`, using
  the placeholder rather than the literal) and run the one targeted test that names the class
  (`python -m pytest tests/test_rename_llgenie_serve.py -q`) — seconds versus a matrix. Doubly
  self-referential: the lane whose job is tree==live shipped a tree that reds the suite.
- **When the head is stale or wrong and you cannot push yet (a run is `in_progress`), DISARM
  auto-merge so an approval cannot land it; re-arm on the corrected head.** A PR can be armed and
  `REVIEW_REQUIRED` at once; if its tree went stale (live moved) or red while you wait for the run to
  conclude, an owner approval plus a green check would merge the stale or wrong tree. `gh pr merge <n>
  --disable-auto`, fix and rebase on the corrected head, push once it is safe, then `gh pr merge <n>
  --squash --auto` and read `autoMergeRequest` back. A fleet automation sweep can re-arm a disarmed PR,
  so re-read `autoMergeRequest` after disarming and re-disarm if a tick put it back.
- **`.status` on a run lags its jobs; read the jobs, not the run.** A run answers `queued` for many
  minutes while its jobs are plainly `in_progress`, and a `queued` run with twenty completed jobs
  means only lag. Poll `gh run view <id> --json jobs` and count `done/total` plus every job whose
  conclusion is neither `success` nor `skipped`.
- **A stray local `main` branch shadows `origin/main` and makes a rebase land on a stale base.**
  `git branch -a` showed `main` (a local branch) plus `remotes/origin/main`, so `git rebase origin/main`
  and even `git fetch origin` resolved `origin/main` to the stale local one (the "refname 'origin/main'
  is ambiguous" warning is the tell). GitHub then reported the PR `CONFLICTING` with no run and no CI,
  and `git merge-tree` at the true tip was clean. Fix: `git fetch origin refs/heads/main:refs/remotes/origin/main`
  and rebase onto `refs/remotes/origin/main` explicitly, never the ambiguous shorthand.
- **Never round-trip the doc through `read_file` → `write_file`.** `read_file` numbers and
  truncates lines; writing that back silently deletes the tail of a 1000+ line document. Use
  `patch` with a unique anchor for every edit.
- **A stuck job is not a failed run: cancel the run, then rerun only that job.** `gh run rerun <id>
  --job <jobId>` refuses while the run is in progress, so the recipe is cancel → job id → rerun that
  job; the other jobs keep `success`, so one green rerun makes the run green at the same head. **Calibrate
  before calling anything hung:** `linux / unit` measures ~1h45, so 30-60 minutes is on schedule, and any
  timeout ceiling proposed for it must be ≥150 minutes — a 60-minute ceiling reds a *passing* run. Ask the
  owner before declaring a job hung, and tell the fleet *before* cancelling (a cancel reads like a
  failure). Which symptom is which — hang, sweep, capacity, live-data drift, a base-branch gate — is
  the table in `references/ci-triage-for-docs-prs.md`.
- **Pushing while the head's run is `queued` is safe; pushing while it is `in_progress` is not.** A
  queued run has done no work, so a new commit supersedes it harmlessly — that is the window to add a
  last commit to a PR. Once any job is running, `cancel-in-progress` makes the same push destructive:
  finish the  run, merge, and carry the extra commit in a follow-up PR instead. Read
  `gh run view <id> --json jobs --jq '[.jobs[]|select(.status=="in_progress")|.name]'` before deciding.
  **When the pending commit is a live→tree fold the PR cannot merge without** (the tree is stale and the
  drift gate reds on it), do not idle and do not cancel the run to free the branch: build the fold
  **locally** — functional commit, battery measured at that local head, then the prose-only record
  commit — keep the PR-body edit staged but unapplied (a body naming a head that was never pushed is a
  lie), and push as the next head the moment the in-flight run concludes, letting a fresh matrix give
  the merge verdict. A run at a head you know will be superseded is not wasted work when its question
  was behavioural (does the new ceiling complete or cancel); cancelling it to save queue time throws
  away the only measurement it was launched to produce. **Re-run the live↔tree comparison immediately
  before that deferred push** (`make sync-agent-profile PROFILE=<p> CHECK=1` plus a byte size on both
  copies): live is written while you wait, so a copy that was identical hours ago can be the stale
  snapshot the drift gate reds on main — fold the new growth before pushing, not after the matrix.
- **One occurrence per canonical rule — a count is not a dedupe.** Copying #873's fence *and* keeping a
  lane-section restatement of the same rules leaves every rule twice, and the two copies then drift by
  a full stop while each still "appears once" to a grep on a single spelling. After any fence re-sync
  assert two things, not one: `fence in soul` is True **and** each canonical rule phrase occurs exactly
  once (`live.count("Never hold a PR without a remedy") == 1`, etc.). Delete the restatement, keep the
  fence, and never leave two headings that both claim to hold the rules. Size proves nothing in either
  direction: a tree copy that was *larger* than live still dropped lines, and a live copy that is larger
  may be holding every rule twice.
- **The fence's verbatim test is against `agents/standing-rules.md`, not #873's issue body.**
  `check-agent-profiles` compares `_stated_block == fleet_block()`, and the canonical the gate reads is the committed
  `agents/standing-rules.md` — which can drift from the issue body the lane copied from. A block that is byte-verbatim
  to the issue and whose rules each appear once can still red the gate as "fleet-block-drift" because the *words* of
  four canonical bullets are a paraphrase. So after re-deriving a fence, assert it against the gate's file — the
  implementer's comparator `_stated_block == fleet_block()` — before declaring `block in soul == True`, and when the
  two disagree, re-type from `agents/standing-rules.md` rather than trusting the count.
- **To make a lane's SOUL state the canonical fleet block verbatim, relocate ONLY the extras — moving whole bullets that restate canonical rules reds the duplicate gate.** A SOUL's `## Standing rules (fleet…)` section is often interleaved with lane-specific material: an appended sentence inside a canonical bullet, a lane *variant* of a canonical rule (e.g. a different "Arm…" bullet), and extra `#`-cited bullets. Set the section body to the exact text of `agents/standing-rules.md`, and put the lane-specific material in a separate `## Lane rules (<profile>)` section. Do **not** relocate the modified *full* bullet — that duplicates the canonical rule and fails `tests/test_agent_profiles.py::test_the_report_names_duplicate_canonical_rules_and_the_gate_does_not_fail_on_them`; move only the added clause/sentence/clause-bearing bullet, not the whole rule. Verify with `python3 scripts/check_agent_profiles.py check` (no `fleet-block-drift` for that lane) and `python -m pytest tests/test_agent_profiles.py` (the duplicate test included) before pushing. When a `## This lane` heading immediately follows a bullet, add the blank line the markdown linter wants in the same edit.
- **A PR's head may live on the FORK, so `git push origin HEAD:<branch>` can leave an existing PR unmoved and create a stray upstream branch.** `origin` is the upstream (`asimov-agent/llgenie`) but an existing PR's `headRepository` is often the fork (`andyholst/llgenie`). Pushing to `origin` then prints `[new branch]`, creates the branch on the upstream, and **the PR head does not change**. Check `gh pr view <n> --json headRepositoryOwner,headRepository` first; push to `fork` (`git push fork HEAD:<branch>`), delete the stray (`git push origin --delete <branch>`), and confirm the head moved (`gh pr view <n> --json headRefOid`). **This applies only to a PR that already exists** — for a brand-new branch there is no PR head yet, so pushing to `origin` (upstream) and `gh pr create --base main --head <branch>` records a same-repo head and is valid; verify it with `gh pr view <n> --json headRepositoryOwner,headRefOid` after creation. Read `git remote -v` before deciding, not a remembered layout.
- **Do not re-derive a bot's numbers by hand in prose.** Copy them from a command output you just
  ran, and quote the command in the PR body so a reviewer can reproduce it.
- **A raw audit is mostly false positives — filter before you report or file anything.** Only
  hyphenated `make` tokens that match a target or a `target-%:` pattern are commands (the words
  after "make" in prose are not, and `build-engine-<engine>-<arch>` is legal because the Makefile
  has `build-engine-%:`); a workflow `*.yml` a doc cites may belong to the *model* repo
  (`qa-validate.yml` lives in `trending-local-llms`), so "no local file" is not by itself a
  defect; and `docs/BOTS.md` states cadence as `:43`/odd-minute prose in places and as a cron
  expression in others, so match the table, not the regex. One check in `scripts/docs_audit.py` is
  known to false-negative: "engine-gap census present in ARCHITECTURE.md" compares a single-line
  string against text the doc wraps across lines, so `False` there means "wrapped", not "missing" —
  confirm by grep'ing the first three words before acting on it. **The census checks in that script
  compare against `HEAD`, but since #1053 `docs/ARCHITECTURE.md`'s census is *referent*-based (it
  names a `measured at <sha>` and describes THAT tree) — so `claim present [tracked files]: False`
  (and the agent-wiki siblings) while the doc's pointer is an ancestor other than `HEAD` is
  EXPECTED, not a defect; trust `make check-architecture-census` (which reads the referent) over the
  audit's HEAD-based census lines.** `scripts/docs_audit.py` bakes the
  other filters in — extend it rather than growing another one-off grep.
- **A stacked PR is never merged before its base — a squash would land the base's files.** When the
  `agents/` tree (or any larger change) is still unmerged, lanes stack their small PRs on that
  branch, and the PR then shows a base commit plus their own file. Merging it into `main` alone
  squashes the BASE PR's whole diff into `main` under this PR's name. Check the base commit is an
  ancestor of `origin/main` (`git merge-base --is-ancestor <base> origin/main`) before merging; if it
  is not, the PR waits, and says in its body which PR it is stacked on and that it must not land first.
  A stacked PR also **inherits the base branch's gate failures**: `check_pr_authors` reads
  `origin/main..HEAD`, so one commit on the base authored outside the allowlist reds your PR even when
  every commit of yours is valid. That fix belongs to the base's lane — name the offending sha and who
  owns it in the body rather than re-authoring someone else's history.
- **Never `cp` a whole shared doc between worktrees or over main's copy — insert your sections by
  heading anchors.** `docs/BOTS.md` (and `docs/ARCHITECTURE.md`) receive commits from every lane, so
  copying a file from an older base silently deletes the sections the tree gained since then
  (a `worktree-report` target, a #992 note) and `check-docs` reds on the very target the copy erased.
  When you carry a doc change to a branch that has moved: `git checkout -- <doc>` back to `origin/main`,
  then slice-in **only** your owned sections using each heading as an anchor —
  `out = main_b.replace(GREEN, enrolled_sections + "\n" + GREEN, 1)` where the enrolled sections are
  contiguous `heading → next-heading` slices of your working file taken in file order (never by
  crossing anchors, or the slices overlap and duplicate each other). Verify by counting **your section
  headings** on the result (`the four headings each present exactly once`), and confirm `check-docs`
  still passes else the copy dropped the tree's own rows. Size says nothing — a byte count cannot tell
  a section you added from a section you erased.
- **Recover a file lost to a branch reset from the object store — never re-author from memory.**
  `git reset --hard` or a `rebase --abort` removes your working text, but the blob you committed stays
  in the object database until gc; worktrees added with `git worktree add` share that store, so a commit
  you made in one (and reset) is still addressable from the main repo. `git fsck --no-reflogs --unreachable
  | grep commit`, then `git cat-file -t <sha>` to confirm, and `git show <sha>:<path>` retrieves the exact
  bytes. Re-authoring a long doc section from memory is how a file drifted by a full stop — recover it.
- **Resolve the rendered `CHANGES.md` conflict by regenerating, never by hand.** A `UU CHANGES.md` on a
  rebase is expected every time the base gained fragments: `git checkout --ours CHANGES.md` (keep the
  base's render), then `make -s changes-index` which rewrites it from the new base's fragments plus
  yours, `git add` that render and `rebase --continue`. (`make changes-index` renders the whole file
  from every fragment in `docs/changes.d/`, so which side you start from does not matter — the
  regeneration is what makes my row AND the concurrent lanes' rows appear.) Never hand-merge a
  generated file — a manual edit that stops matching the fragments reds `check-changes` inside the next
  `check-docs`. **`git rebase --continue` in a non-interactive terminal opens `$GIT_EDITOR` and HANGS**
  — the foreground cap fires with no output and the rebase stays paused (the tell is a `rebase-merge`/
  `rebase-apply` dir still present). `export GIT_EDITOR=true` (or `git -c core.editor=true rebase
  --continue`) first so it reuses the recorded commit message; re-running the capped command with the
  editor forced completes it immediately. **Verify byte-identity of your own files only AFTER
  `--continue` finishes, never in the paused conflict state** — a `cmp` live-vs-tree during the pause can
  misreport a mismatch on a file the rebase auto-merged correctly, and chasing that false mismatch is a
  wasted resolution pass.
- **After a merged PR carries part of your staged doc work, drop that part before shipping the follow-up.**
  When a PR that rode in merged one of the sections you were going to add, a follow-up that re-adds it
  duplicates a sentence already on `main`. Re-fetch `main`, and for each section you planned to add run
  `grep -c '<heading>' docs/BOTS.md` on the fresh copy — if it is present, cut it from your branch, note
  in the PR body that it arrived with the merge, and ship only what `main` lacks.
- **Before implementing an issue, find the PR that already closes it.** `gh pr list --repo
  asimov-agent/llgenie --state open --search '<n> in:body' --json number,title` lists lanes that are
  already implementing it, drafts included, and their `files[]` says whether they touch the page you
  are about to edit. Two lanes writing the same doc row is a rebase conflict and a wasted PR; a
  confirmation comment on the issue is the correct contribution from the second lane.
- **A new `make` gate the docs lane must own: `check-wiring` refuses it unless a CI job calls the target DIRECTLY.** Wiring the check into another target's recipe (e.g. `check-docs` runs it) is not enough — `check-wiring` faults a target whose `##` help claims CI coverage when no `ci-*` job invokes it by name, because the wiring check does not traverse one target into another. Fix: add `$(MAKE) check-<gate>` to the `ci-*` job's recipe that a pipeline job actually runs (e.g. `ci-unit`), give the target a `##` user-facing help line, and register it in `.PHONY`. A gate that changes `scripts/`, `Makefile` or a workflow also needs an OpenSpec change (`openspec/changes/<name>/{proposal.md,specs/<cap>/spec.md,tasks.md,.openspec.yaml}`) validated with `make openspec-validate NAME=<name>` — the fragment-only `docs/changes.d/` shortcut covers doc changes, not code ones.
- **A gate that will police your change may still live in an unmerged PR — prove your head green under THAT version before it lands, or the race reds you.** Your CI is green today only because the new gate is not on `main` yet; if the gate PR merges first, a re-run reds your untouched head. Fetch the gate PR's head and run its checker against your own worktree: `git fetch origin +refs/pull/<n>/head:refs/remotes/origin/pr<n>`, `git show origin/pr<n>:scripts/check_docs.py > /tmp/gate.py`, then `PYTHONPATH="$PWD:$PWD/scripts" python3 /tmp/gate.py check --root "$PWD" --base origin/main`. Two gotchas: the checker imports sibling modules (`changes_index`) from `scripts/`, so `scripts/` must be on `PYTHONPATH` or it dies with `ModuleNotFoundError` — and your *own* branch's `check_docs.py` may still reject `--base` ("unrecognized arguments") until the gate PR merges, which is exactly why you run the PR's file, not yours. Exit 0 there is the proof the gate will not bite your head; add the missing note/fragment now rather than after the merge.
- **A census a gate asserts must be measured at the FINAL PR head, not the base you branched from.** When the change adds tracked files (a new script, an OpenSpec change dir, a note, a fragment), the count at the merge base is stale the moment you commit. Write all the assets, commit once, then measure at that head and set the document's numbers to it — never compute them from the pre-commit tree and assume the operand files don't move the total. The gate turning green at the committed head is itself the proof the numbers match.
- **Every "verified at `<sha>`" sentence must be true AT that sha — name the sha you actually ran the command on, never the branch head you assume is equivalent.** A note claiming "the battery passed at the final head `X`" while the check actually errored at `X` and passed at an earlier `Y` is the same defect as a census with no `measured at`: it reads as proof and is a coincidence. The safe shape when a commit must follow the measurement is a **prose-only follow-up commit** whose subject says it records the battery run at the earlier sha — the numbers were measured on a completed run, so a later edit cannot retroactively falsify them. When a late commit genuinely changes the tree, re-run the battery and update the sha; never delete the evidence paragraph to escape the mismatch, because the record's whole purpose is that proof.
- **Adding a gate to a `ci-*` job also needs it classified in `scripts/issue_bot_gates.py` — and only the FULL suite tells you.** After `check-wiring` is satisfied (line above), a new `$(MAKE) check-<gate>` in `ci-unit` still reds `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired`: the guard faults any `ci-unit` gate that is neither in `FAST_GATES` nor in `DEFERRED`. `FAST_GATES` is the pinned #475 six — never widen it; add the gate to `DEFERRED` with a one-line reason instead. The fast gates (`lint check-docs check-wiring`) do **not** run this test, so a `scripts/`/`Makefile` change is not done until you run the full `make test-unit` (or at least `python -m pytest tests/test_issue_bot_gates.py`) — a green fast-gate set is not a green suite.
- **A census's `measured at <sha>` pointer is a real, reachable commit whose tree COUNT equals `HEAD` — not a sha string equal to `HEAD`.** The literal `pointer == HEAD` check is unsatisfiable for a document that lives inside the tree it measures (every commit that updates the pointer re-heads it). Implement it as: the pointer resolves to a real commit (`git cat-file -e <sha>^{commit}`, so an amend-orphaned sha reds), and `git ls-tree -r --name-only <pointer> | wc -l == HEAD` — so the census describes the tree the gate sees and reds only when a real file is added. And after a **squash-merge onto a `main` that moved** between your push and the merge, the merged tree can be larger than your branch's (other PRs' files land under the squash): `main` then reds until a refresh — file that refresh as its own issue with the measured delta; it is the gate working, not a defect in your PR.
- **When a gate reds on a tree you did not branch from, prove it is upstream by running the SAME gate on a pure `origin/main` worktree before blaming or fixing your diff.** A census pointer left on a pre-squash commit reds `check-docs` on every branch, including PRs that touch no census file — the pointer names a commit the branch does not contain. Cut a scratch worktree at fresh `origin/main` (`git worktree add /tmp/mt origin/main`), run `make -s check-docs` (or the one gate) there, and quote both outputs: a red on the pure-main tree proves the defect is upstream and belongs to its own issue (route it to the generator's owner), NOT to a `do-not-merge` on your PR. Do not disarm the PR, rebase-loop it, or hand-edit the pointer to force green — one shared upstream red is one issue and one fix, and it clears for every open PR the moment that fix lands. The same move applies to any gate: an unrelated tree reds it, so the pure-base run is the discriminator between your diff and the tree. For a `check-docs` red, classify the census pointer with `git cat-file -e <sha>^{commit}` before fixing — non-zero means a sha no commit ever had (a hand-edited pointer, not a squash orphan), and the re-point recipe is in `references/docs-freshness.md`.
- **Rebasing onto `main` after the base PR was SQUASH-merged replays far too much — cut fresh, or `--onto` your own base.** A branch cut from a PR head that later merges as a squash is not an ancestor of `main`, so `git rebase origin/main` finds a much older merge-base and replays hundreds of commits, colliding on every shared file (`Makefile`, `agents/*`). Safe shapes: `git checkout -b <new> origin/main` then copy/apply only your own files (clean when the merged blobs equal your base's), or `git rebase --onto origin/main <the-sha-your-branch-was-cut-from>` which replays only `base..HEAD` (your own commits). A one-commit replay on a one-file change is the signal it worked; confirm the count before pushing.
- **A repository-wide queue stall is capacity, not a red check — do not rerun-loop it.** A run at
  `guard` with `0/N` jobs plus dozens `queued` repo-wide and ~zero `in_progress` means nothing is being
  scheduled (`gh api "repos/<repo>/actions/runs?status=queued&per_page=1" --jq .total_count`). Rerun,
  cancel and dispatch all add to that queue, and an empty commit corrupts the head: report it and
  produce local evidence instead. The commands, and the rule that a partial local run is reported as
  partial and never rounded up to "suite green", are in `references/ci-triage-for-docs-prs.md`.
- **A docs-only PR that reds a *data* gate is misattributed by default — prove it before fixing.**
  `check-trend-list-matrix` (and its siblings) compare a committed fixture against a list derived from
  the live registry, so CI can answer `fixture is stale` while the same head passes locally. When a
  job fails on a gate that reads `data/` or the network and your diff touches only `docs/**`,
  `agent-wiki/**`, `docs/changes.d/**` or `CHANGES.md`, run that one gate locally at the same head
  (`make -s check-trend-list-matrix`), quote both outputs in a PR comment, and recover with
  `gh run rerun <id> --failed` — same head, no new commit, no cancelled matrix. Two reds on the same
  live-data gate means the fix is upstream, not a rerun loop: say so on the tracking issue and keep
  your PR open rather than landing behind a flaky green.
- **A live→tree skill sync copies ONE directory, never the live `skills/` root.** The live profile's
  `~/.hermes/profiles/<profile>/skills/` is the shared store — every skill the host has installed, not
  just the lane's own. `cp -a "$L/skills" "$T/agents/<profile>/"` therefore mirrors hundreds of
  foreign skills into `agents/<profile>/skills/**` and turns a five-file sync into a tree-wide diff
  that CI and the drift gate both read as a lane shipping skills it does not own. Copy the lane's own
  bundle only (`cp -a "$L/skills/llgenie-docs-maintainer" "$T/agents/<profile>/skills/"`) and confirm
  `git status --porcelain agents/<profile>/` lists exactly the files you meant to version — a stray
  `curator/`, `_runtime/` or another lane's skill dir is the tell, and it is removed from the worktree
  only, never from live.
- **A branch of yours that reds `check-import-roots` is usually your own new test — fix the import, never the baseline.** The ratchet (issue #796) records counts in `tests/fixtures/import-roots-baseline.json` (`bare` / `sys-path`) and exits 1 the moment a count RISES, so a PR that adds a test inserting its own `sys.path` entry or importing a `scripts/` module bare (`import check_docs`) reds `ci-unit` even when every other job is green — the failing site it names may be an OLD offender, not your file, because it lists all sites. The allowed shape is the conftest seam: `from scripts import check_docs` (sibling `tests/test_check_docs.py` shows it). A baseline is a measurement and may fall, never rise, so the fix is the import in the PR, never a fixture bump. Verify with `python3 scripts/check_import_roots.py ratchet` on the branch before pushing — and read the exit with `echo ${PIPESTATUS[0]}`, not `$?` after a pipe.
- **A `pull_request` run evaluates the workflow at its MERGE REF (head merged into base), so a CI-ceiling raise merged on main does NOT apply to an unrebased PR — its runs are judged against the ceiling text at its BASE.** A `linux / unit` `completed/cancelled` at ~60 min with zero test output and siblings green is the OLD-ceiling fingerprint when the PR's base predates the ceiling merge — not (necessarily) starvation, and not a defect. Diagnose before any rerun: `gh pr view <n> --json baseRefOid` vs the ceiling-merge sha on main. Recovery is a rebase onto the fresh main + `--force-with-lease` (own branch) so the fresh run evaluates at the new ceiling — do NOT `gh run rerun` a run doomed by the old ceiling (it replays the recorded 60 and lands a second identical cancel that reads as starvation on the ledger), and if you already reran by mistake, cancel your own rerun rather than feed the ledger another copy.
- **A cancel is three classes, not one — identify it before acting, and never push an unclassified one into the starvation ledger.** Old-ceiling (base predates the ceiling raise), starved runner (~1h on a ~1h45 job, `Timeout (0:05:00)!` in the step log, siblings green), and the third: **a short cancel (~25-30 min) of the long job with every sibling green, no `concurrency:` block at the base, and a `head_sha` already superseded** — that is an owner/API cancel of a vanity run, so nothing to rerun and nothing wrong with the diff; the deferral it justified is over and the push is safe. Always read `head_sha` before treating an `in_progress` run as "the head's run": a leftover run pinned commits behind cannot be destroyed by pushing the current head. **And when you list runs by `head_branch`, compare each `head_sha` to YOUR head before attributing anything** — `gh api "repos/<r>/actions/runs?head_branch=<b>"` can return runs whose `head_sha` is an unrelated commit (another lane's PR sharing the branch-name filter, or a pre-fix push), so a red `ci-scope` in that list may belong to a commit that is not your head; confirm `git merge-base --is-ancestor <that-sha> <your-head>` is false before discounting it as noise. Report such a cancel as *unclassified* with its measurements — the class table and commands are in `references/ci-triage-for-docs-prs.md`.
- **Search the open issues before filing the gap you just measured.** The audit findings are
  exactly what the repo's triage legs file, so `gh issue list --repo asimov-agent/llgenie --state
  open --search '<page/metric>'` first; if an issue exists, verify its quoted numbers against the
  current tree and comment the confirmation instead of opening a duplicate (which the dedupe leg
  will close into the original anyway).
- **Keep long audit commands out of a single `terminal` call.** A multi-statement shell one-liner or
  heredoc can trip the oversized-payload guard and get blocked outright; the audit belongs in the
  skill's `scripts/` file, one command, no payload. Same for anything you will run twice.
