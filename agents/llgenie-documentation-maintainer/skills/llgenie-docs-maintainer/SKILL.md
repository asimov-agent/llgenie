---
name: llgenie-docs-maintainer
description: "Use when auditing, filing or landing LLGenie docs changes."
version: 1.0.7
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

Concretely, treat this as part of comparing the behaviour of existing issues and their implementations:

- `make check-agent-profiles` names the gaps: `live-longer`, `live-edited-not-tree`, `fleet-block-drift`
  (the last is tree-only and reds CI; the first two need a live profile, so CI never sees them).
- `make sync-agent-profile PROFILE=<p> CHECK=1` byte-compares the tree copy to live — exit 0 means the
  pair is identical, a `differ` line names the first divergent file.
- **Direction is judged on content, per hunk, never copied blindly:** a tree copy that is a *prefix* of
  live means live is newer — re-take live→tree; a live file edited *after* the tree commit means the
  lane's behaviour outran the repo — commit it via an issue+PR under `agents/<profile>/`.
- **Never run `sync-agent-profile` in write mode for a lane whose live is richer** — it truncates and no
  gate notices (#791). `CHECK=1` only.
- **Re-copy live→tree at PR time, not when you cut the branch.** A versioning PR stays open while the
  lane keeps editing its live skill, so a tree copy committed early is already stale by merge (live
  gained lessons twice during one PR) and `sync-agent-profile CHECK=1` then reds on `main` against
  the newer live. Re-run the live→tree copy and `CHECK=1` at the final head before pushing/landing;
  if a held branch's snapshot is behind, re-copy — do not ship the stale snapshot.
- A gap found while reviewing someone else's PR is a **new issue**, scoped to the owning lane; the docs
  lane writes the fix only under explicit dispatch (name the delegation in the PR body — e.g. #1062 to
  the planner, #885 to the rebase lane).

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
sha, what changed, the run id or command that proves the numbers. In this lane the rule lands in the
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
the review/check requirements clear. Read it back — `gh pr view <n> --json autoMergeRequest` — and quote
`enabledAt` in the report, because "I armed it" without the timestamp is the same unverifiable claim as
"CI looks green".

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
   commit — then `git push --force-with-lease=<branch>:<old-remote-sha> origin HEAD:<branch>`.
8. Update the PR body (`gh pr edit --body-file`, then **read it back** and grep for the new head
   and `closes #<n>`). If another open PR edits the same doc, name it in the body and state the
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
  `make changes-index-report` prints how far behind it is; the docs lane refreshes it.
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
  `CHANGES.md` are exempt. Assert the surface set **additively** — a behaviour/subset check, never a
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
- In this checkout `origin` is the upstream (`asimov-agent/llgenie`) and `fork` is
  `andyholst/llgenie` — check `git remote -v` before pushing; a PR head is `andyholst:<branch>`.

## Pitfalls

- **`gh pr checks` lags the push by a minute and then lies.** Right after a push it prints
  `no checks reported on the '<branch>' branch`; the run exists. Use
  `gh run list --repo … --commit <sha> --json databaseId,status,event` and poll
  `gh run view <id> --json status,conclusion,jobs` instead. Jobs can sit `queued` for minutes on
  a starved runner — that is not a red check. To wait on a long run, start
  `gh run watch <id> --interval 60 --exit-status` in the **background** and let its completion wake
  you; a foreground `sleep`/poll loop is clamped (~3 min) and dies mid-wait, which reads like the
  run failed when nothing happened.
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
  <cancelled-run-id>` at that same head — **never push** — then confirm the gate has a real
  conclusion in a completed run before calling it green or red.
- **`closingIssuesReferences` is eventually-consistent — a `none` right after a PR is created is not evidence the `Closes #<n>` keyword failed.** The field is populated asynchronously, so `gh pr view --json closingIssuesReferences` returns empty for minutes after creation; do **not** edit the body in response. Re-read later, or confirm the link from the body text and the issue's own timeline. A positive is proof; a negative is only "not yet, or genuinely absent".
- **A local full `make test-unit` pass is evidence, not the CI verdict.** CI runs with a clean HOME where live-vs-tree profile comparison is skipped, so a test that reads the host profile can pass locally for a different reason than CI runs it (or vice versa). Report a local suite as evidence — its exit code and the head sha — and still wait for the CI job's own conclusion before calling a head green; the two can disagree, and the CI one is the one that gates.
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
  finish the run, merge, and carry the extra commit in a follow-up PR instead. Read
  `gh run view <id> --json jobs --jq '[.jobs[]|select(.status=="in_progress")|.name]'` before deciding.
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
- **A PR's head may live on the FORK, so `git push origin HEAD:<branch>` can leave the PR unmoved and create a stray upstream branch.** `origin` is the upstream (`asimov-agent/llgenie`) but a PR's `headRepository` is often the fork (`andyholst/llgenie`). Pushing to `origin` then prints `[new branch]`, creates `agents/…` on the upstream, and the PR head does not change. Check `gh pr view <n> --json headRepositoryOwner,headRepository` first; push to `fork` (`git push fork HEAD:<branch>`), delete the stray (`git push origin --delete <branch>`), and confirm the head moved (`gh pr view <n> --json headRefOid`).
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
  yours, `git add` that render and `rebase --continue`. Never hand-merge a generated file — a manual edit
  that stops matching the fragments reds `check-changes` inside the next `check-docs`.
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
- **A census a gate asserts must be measured at the FINAL PR head, not the base you branched from.** When the change adds tracked files (a new script, an OpenSpec change dir, a note, a fragment), the count at the merge base is stale the moment you commit. Write all the assets, commit once, then measure at that head and set the document's numbers to it — never compute them from the pre-commit tree and assume the operand files don't move the total. The gate turning green at the committed head is itself the proof the numbers match.
- **Adding a gate to a `ci-*` job also needs it classified in `scripts/issue_bot_gates.py` — and only the FULL suite tells you.** After `check-wiring` is satisfied (line above), a new `$(MAKE) check-<gate>` in `ci-unit` still reds `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired`: the guard faults any `ci-unit` gate that is neither in `FAST_GATES` nor in `DEFERRED`. `FAST_GATES` is the pinned #475 six — never widen it; add the gate to `DEFERRED` with a one-line reason instead. The fast gates (`lint check-docs check-wiring`) do **not** run this test, so a `scripts/`/`Makefile` change is not done until you run the full `make test-unit` (or at least `python -m pytest tests/test_issue_bot_gates.py`) — a green fast-gate set is not a green suite.
- **A census's `measured at <sha>` pointer is a real, reachable commit whose tree COUNT equals `HEAD` — not a sha string equal to `HEAD`.** The literal `pointer == HEAD` check is unsatisfiable for a document that lives inside the tree it measures (every commit that updates the pointer re-heads it). Implement it as: the pointer resolves to a real commit (`git cat-file -e <sha>^{commit}`, so an amend-orphaned sha reds), and `git ls-tree -r --name-only <pointer> | wc -l == HEAD` — so the census describes the tree the gate sees and reds only when a real file is added. And after a **squash-merge onto a `main` that moved** between your push and the merge, the merged tree can be larger than your branch's (other PRs' files land under the squash): `main` then reds until a refresh — file that refresh as its own issue with the measured delta; it is the gate working, not a defect in your PR.
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
- **Search the open issues before filing the gap you just measured.** The audit findings are
  exactly what the repo's triage legs file, so `gh issue list --repo asimov-agent/llgenie --state
  open --search '<page/metric>'` first; if an issue exists, verify its quoted numbers against the
  current tree and comment the confirmation instead of opening a duplicate (which the dedupe leg
  will close into the original anyway).
- **Keep long audit commands out of a single `terminal` call.** A multi-statement shell one-liner or
  heredoc can trip the oversized-payload guard and get blocked outright; the audit belongs in the
  skill's `scripts/` file, one command, no payload. Same for anything you will run twice.
