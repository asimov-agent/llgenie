---
name: github-issue-triage
description: Use when triaging open issues that have no PR.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [github, issues, triage, bots, gh]
---

# Issue triage: the repo's open issues that carry no PR

## When to Use

"Act as the issue bot", "go over the issues without a PR", "what is already being worked on", "refine /
implement / close what no longer makes sense", "is this issue still valid?". Also the planner shape of the
job — verdict every open issue, then hand each verdict to the bot that will do the work (in-repo CI bot by
label, or a host implementer profile by `message_agent`). Not for planning a project as an issue tree, and
not for PR review (see the `github` skill for the gh surface itself).

## Status sweep: what is already in flight (do this first)

When the ask is "go over the issues" / "what is being worked on", do not read issue text — enumerate state
three ways and join it in code:

1. **Open issues + comments**, redirected to a FILE: `gh issue list --repo <o>/<r> --state open --limit 300
   --json number,title,labels,assignees,createdAt,updatedAt,comments > /tmp/issues.json`, then `json.load`
   it. Redirecting matters: comment bodies carry raw control characters and long markup, so
   `json.loads(stdout)` dies on `Invalid control character at: line 1 column …`. Sort and group in Python
   from the file rather than reading by eye.
2. **Open PRs:** `gh pr list --state open --json number,title,headRefName,mergeStateStatus,author` — an
   issue whose PR is open is not a candidate at all.
3. **Bot branches:** `gh api repos/<o>/<r>/branches --paginate --jq '.[].name' | grep -E 'agent/issue'` —
   a branch for a closed issue, or for an open issue with no PR, is the queue re-offering stale work.

Then put every open issue in exactly one bucket: **held** (live claim), **claimed-but-stalled** (expired
claim, or a run that pushed a branch and opened no PR), **queued** (an `agent:implement`-style label, no
claim), **orphan branch**, or **idle**. Claim format, TTL arithmetic and the sweep one-liners:
`references/bot-claim-and-branch-sweep.md`. Report in that shape: what is genuinely in flight (usually one
or two items), then the grouped backlog, then the concrete next actions — the user asked for a status
read, not a verdict per issue.

## Procedure

1. **Enumerate from the timeline, not the issue text.** For every open issue read
   `repos/<o>/<r>/issues/<n>/timeline` and keep only the `cross-referenced` events that carry a
   `pull_request` URL; an issue with none is a candidate. Script + batching notes:
   `references/no-pr-enumeration.md`. An issue body can say "no PR" while a merged PR already closed the
   class — the timeline is the only honest source.
2. **Read each candidate's body before judging it.** Bot-filed "run failed" issues carry the workflow,
   run id, failing job/step and a log tail. That job + first assertion line is the evidence your close
   comment quotes, and it is also what separates obsolete from still-valid.
3. **Assign one verdict per issue, all of them before the first write:**

   | verdict | test | action |
   |---|---|---|
   | obsolete | the guard/test/commit that fixes it is on `main` | close, citing `path:line`, the commit and the guard test |
   | duplicate | another open issue owns the class | close, naming the canonical issue and why this instance is not separate |
   | superseded | a later run of the same workflow went green, or the run's PR merged/closed | close; cite the green run or merged PR |
   | by design | the failure is what the repo mandates | close quoting the rule, plus the filing defect if any |
   | still valid | the claim still reproduces on `main` | refine the body (scope delta) or implement it |

   Verify the claim instead of trusting it: `grep -n '<symbol>' scripts/`, `git show <sha> --stat`, and
   `gh run list --workflow <wf> --limit 6` — green runs after the reported failure are supersede evidence.
4. **Close only with evidence.** A close whose comment does not point at the code, commit or green run that
   made the issue moot is noise the next reader has to re-derive.
5. **Refine is a body EDIT, and entangled defects split into separate vehicles.** A refinement the
   implementer can act on is an edit to the issue BODY (`gh issue edit <n> --body-file <refined.md>`), never
   a restating comment — the body is what the implementer opens, so a comment leaves the unshaped original
   standing. When the issue packs two defects with different root causes, fixes and refs into one body (a
   tell: "fix direction to be decided"), split it into two explicit vehicles IN the refined body — one
   acceptance list each plus a hard "never one PR for both" clause — because one vehicle for two root
   causes yields a PR nobody can review and a gate neither fix owns. Prove the shape landed by reading the
   body back as a BOOLEAN ARRAY: `gh issue view <n> --json body --jq '[(.body|contains("## Acceptance
   criteria"))]'` — do not concatenate a string and a number with `+`, jq throws "cannot add: string and
   number" and the verify step reads as a failed edit. When most of an issue has already landed (one flag
   exists, the status list does not), rewrite what is left as the remaining bullets plus a suggested title,
   and set the order in which related issues should land (policy issue first, then the data, then the
   wiring).

   **An `agent:implement` issue with no acceptance section and no open PR is a REFINE, not a dispatch.**
   Before handing any issue on, check both: `gh pr list --search "(<n> in:body)" --state open` (searches PR
   bodies, so it also catches a vehicle whose branch is not `agent/issue-<n>-*`) and whether the body carries
   an `## Acceptance criteria` / `## Goal` heading. An unrefined, unowned issue handed straight to an
   implementer burns a whole run on a brief that still says "to be decided" — restate it into the six-section
   shape and edit the body FIRST, then dispatch.
6. **Implement at most one issue per branch and PR**, OpenSpec change first where the repo uses it, and
   `closes #<n>` only when the PR implements the whole issue.

## Pitfalls
- **The reach pin scans only `ut.select()` — `unit-suite.json` exclusions decide what is under the gate.** Before calling any "carve-out" or "unmarked reach" gap in tests/test_network_marker.py a real hole, check tests/fixtures/unit-suite.json: a file listed under `excluded` (e.g. → test-strata-live, test-install-trend) runs in the network seam and is NEVER scanned by the pin, so zero marks there are expected, not a defect. Reusing that premise twice (2026-10-31, #1000 carve-out) produced a wrong architect dispatch.
- **A "NOT X called DIRECTLY" comment in a gated test is often a deliberate, merged decision — diff the merge commit before proposing to close it.** d86c43bd's 272-line rewrite of test_network_marker.py introduced the plan_download carve-out so ~8 hermetic callers don't false-red; closing it would revert merged work, not fix a gap. A carve-out close is only a real delta if it surfaces an actual unmarked in-unit offender.

- **`gh issue close <n> --comment "…"` is shell-parsed.** Backticks and parentheses in a realistic comment
  kill it (`syntax error near unexpected token '('`). Post the body as JSON through
  `gh api -X POST repos/<o>/<r>/issues/<n>/comments --input -` from a Python dict, then
  `PATCH repos/<o>/<r>/issues/<n>` with `{"state": "closed", "state_reason": "not_planned"}`. Same shape
  for a refine comment (comment only, no state change). If you batch-close through the CLI anyway, define
  `close(){ gh issue close "$1" --repo <o>/<r> --comment "$2"; }` and escape every `$` and backtick in the
  body (`\$(call …)`) — an unescaped `$(...)` in a double-quoted comment is command-substituted, not
  printed. The same quoting trap hits read commands: `gh pr view <n> --json statusCheckRollup --jq
  '… select(.conclusion!="SUCCESS")'` dies with `function not defined` when that filter sits inside a shell
  string — fetch `--json` and compare in Python. And a `--jq` applied to a POST response can error
  (`expected an object but got: array`) while the write itself succeeded, so prove a label or state change
  with a second GET (`gh api …/issues/<n> --jq '.labels[].name'`), never with the POST's own output.
  A hand-built API path also needs its `repos/` prefix (`gh api repos/<o>/<r>/issues/<n>/comments`): drop it
  and every call 404s, which reads exactly like a missing issue — suspect your own path before reporting a
  resource gone. And when a comment you already posted carries a wrong measurement, `PATCH
  repos/<o>/<r>/issues/comments/<id>` to correct it instead of appending a follow-up: the thread is the
  evidence a reviewer quotes, so a wrong line left standing is worse than the retraction.
- **Diff the issue against `origin/main` immediately before writing code, not just at session start.** A PR
  that merged minutes ago often fixes the very thing; implementing first and discovering the landed fix
  afterwards wastes a whole branch, and leaves you filing (then narrowing) an issue about it. `git fetch
  origin main`, grep the symbol the issue quotes, `git log --oneline origin/main -3`.
- **A bot branch already open for the issue may be a RE-implementation of a rule that landed.** The same
  issue can be attempted repeatedly, each attempt renaming the change dir and the symbol (`X_ASK` →
  `Y_ASK`), and the newest attempt can DELETE the tests that lock the landed behaviour — a regression
  dressed as a fix. Before repairing such a PR, `git grep` the rule's symbol on `origin/main`; when it is
  there, close the PR AND the issue citing `path:line` plus the guard test, then delete the branch so a
  sweep cannot resume it (a live branch makes the queue re-offer the issue every hour).
- **A task the run could not complete is OWED, never a quiet tick.** When the repo protects its own
  rulebook (an `AGENTS.md`-style file whose writes need approval), the run cannot land the row its change
  requires. Do not tick the box as done and do not move the row into some other file: record the exact
  intended text in `findings.md`, tick the task with an explicit `— OWED, not applied` clause naming why,
  and repeat that sentence in the PR body so a reviewer can apply it. A silently ticked box is the same
  rulebook drift the guard exists to prevent, one level up.
- **Adding a primitive to a reach set is the OPPOSITE of closing the carve-out — safe, and fileable.** Same file (tests/test_network_marker.py), same symbol (plan_download), but the two directions flip the verdict. *Closing* the carve-out reverts deliberate merged work (d86c43bd) and was correctly killed (2026-10-31). *Adding* `mp.plan_download` to the `_ENTRY_CALL` regex (~:292) + repairing the :268 docstring makes the pin see a primitive it presently cannot — a real guard gap, verified before routing: every in-scope direct caller is already `@pytest.mark.network`. Decide by direction + a false-red check, not by "we already closed this": grep which in-scope files call the symbol, confirm each is network-marked or excluded via unit-suite.json, then route — a latent gap gets its own issue+PR (never rides a closed #1000 vehicle) and LOW priority (no live offender). Filed as #1189.

- **A committed-but-EMPTY fixture stub passes every earlier gate and reds only at the gate that READS it.** A branch adding a snapshot fixture (`tests/fixtures/*-hub-snapshot.json`) containing `{trees:{},searches:{},errors:{}}` looks green until the gate that replays it (`make check-quant-catalog`) runs — and `linux/unit` reaches that gate only after `make test-unit` (cron+check-docs) passes, so the failure appears late and mimics a fresh regression (`HubSnapshotMissing` on the Qwen mlx search). Diagnose by diffing the fixture, not by re-reading logs: `git show <head>:<path> | wc -c` versus the same path on `origin/main` (absent there ⇒ the branch introduced the empty stub). The fix is the owner-approved one-shot live regen (`make sync-quant-catalog`, CI hermetic afterwards), never hand-editing the stub — and the populated snapshot moves the head, so the pre-fix sha must not be armed.

- **A bot claim is a lease with a TTL, not a status.** The claim comment reads `bot-claim: <actor> <ISO>
ttl=<N>m`; it is live only while `now < stamp + ttl`. Compute it against `date -u` instead of eyeballing
the timestamp. An expired claim with a pushed branch and no PR is STALLED work nobody owns — report it as
such, never as "in progress".
- **"changed=true, PR: none opened" in a bot's run summary is a failure mode, not a detail.** The run
  wrote a branch and left no PR, which is exactly what keeps the queue re-offering the issue every hour.
  Sweep those branches together with the ones belonging to closed issues.
- **Check whether the "bots" are local before repeating the user's premise.** An "our local bots are on it"
  reading is usually wrong: the actors are in-repo GitHub Actions (`github-actions` author,
  `issues`/`workflow_run`/`schedule` events), and the Hermes cron store can be empty of any related job.
  Confirm with `gh run list --limit 25 --json name,event,createdAt` plus the actor's login on the issue
  comments, and correct the premise in the answer — a phantom local worker changes who can actually act.
- **A conflicting PR gets no CI run at all.** `mergeStateStatus: DIRTY` means GitHub builds no merge ref:
  `gh pr checks` reports "no checks reported on the '<branch>' branch",
  `repos/<o>/<r>/commits/<sha>/check-suites` is empty, and neither an empty commit nor close+reopen starts a
  run. Rebase onto `origin/main`, resolve, push.
- **Do not add two tests for one rule.** When another change in flight already locked a direction of the
  rule, drop your duplicate and keep only the seam that the other change does not cover.
- **A bot-filed "run failed" backlog is history, not work.** A repo whose failure reactor now skips
  superseded runs (a PR that merged/closed, a push a later run turned green) still carries hundreds of
  issues filed BEFORE that guard existed, and they read like live defects. Verdict them by re-measuring
  the named script on the current tip and by the workflow's runs since — not by the issue's tone.
- **A per-run reactor tracker class collapses to ONE live tracker.** Every failing run of the same
  workflow files "`<workflow>` / `<step>` failed", so a job red for eight runs leaves eight issues with
  byte-identical titles and the same failing step. Close the older ones as duplicates of the NEWEST
  (it carries the run that is still reproducing), and say in each close which duplicate group it
  joined so the group is countable. Do not keep one tracker per run, and do not close the class onto
  a root-cause issue the failure was never filed against. When the tracker's failing steps belong to several
  open issues, KEEP it as the live tracker and answer it with a step → owning-issue table (the step names
  come from `gh run view <id> --json jobs`), so it reads as "these gates are red, each already owned"
  instead of as a defect to implement.
- **A green later run supersedes only if the FAILING STEP actually ran.** Bot legs skip steps by
  verdict: in `issue-bot.yml` a `refine`/`close` triage marks `Implement the issue` and every later
  step `skipped`, so a green run proves nothing about the gate the tracker is about. Check
  `gh run view <id> --json jobs --jq '.jobs[].steps[]|"\(.conclusion) \(.name)"'` and require
  `success` on that step by name (measured: run 40503090552 was green with `Implement the issue` and
  `Re-check the fast gates …` both `skipped`).
- **A gate that fails naming a file and a line is usually working, not broken.** `make
  openspec-tasks-check` exiting 1 with `FAIL <change>: unchecked task checkbox(es) at lines [18]` is
  the repo refusing to push an incomplete change — a `by design` verdict, closed with that log line.
  Run the gate on a clean `main` first: rc=0 there proves the gate is fine and the branch was not.
- **A tracker issue is redundant once its named work item lands.** A reactor-filed issue whose title
  reads `<workflow> / <step> failed` is a tracker: its `**run:**` line names the underlying issue it
  exists for. When that issue is closed and its PR merged, close the tracker as redundant — and
  explicitly name the step-level defect that stays tracked elsewhere, so the close is not read as a
  fix to the step itself.
- **Prove a bot's make target end to end with a fake `gh` on PATH**, and do it for both callers when one
  resolver serves two bots with opposite answers: `printf '#!/usr/bin/env bash\ncase "$1" in api) echo "";
  exit 0;; pr) echo ""; exit 0;; *) exit 1;; esac\n'` into a temp dir, then
  `PATH="$d:$PATH" GITHUB_OUTPUT=<file> make <target> …; echo rc=$?; cat <file>`. That is the exit-code
  contract the workflow depends on, and a unit test on the Python function does not prove it.

- **A doc-refresh issue is superseded by the next refresh, not by the text.** Such an issue names a base
  commit and "last updated at `<sha>`"; run `git log -1 --format='%h %ad %s' --date=iso -- <doc>` and
  compare — a later refresh commit covering a newer tree closes it even when the prose looks unchanged.
  Cite the refresh commit and the PR that carried it.
- **"Residual / could-be-issued" is a claim you must close out before you can call it a finding.** In a close-audit, when you name an issue as "open with a residual" or "worth filing a follow-up for", FIRST check whether its own acceptance is already satisfied on main by merged work — `git show origin/main:<skill>` for the rule/skill it targets, `gh api .../pulls/<fold>` for its stated fold vehicles, timeline rule-out for open PRs. If the shipped tree already satisfies it (fold vehicles merged, tree-versioned skill carries the rules, no open PR), that issue is a close-merged straggler (its merged PR just lacked a `Closes` keyword), NOT a backlog item — close it with the merge-track evidence instead of filing a phantom follow-up that re-works an already-done issue. Grep for the issue's OWN stated content, not some similar phrasing you assumed: a check that greps for the wrong ruleset briefly "finds" a false residual that evaporates once you read the issue body. The completion harness may flag exactly this — an audited-and-named-but-unclosed issue is a real owed mutation, not a misfire.
- **A stale-open issue is itself the defect.** When the fix merges, close the issue with the merge sha in the comment — an issue left open after it is fixed makes every later brief quote a tree that no longer exists, and several lanes will re-report the same "still red" for hours, each spending a turn re-deriving a fact that changed. Symmetric rule for the reverse direction: before quoting any issue as live, `gh issue view <n> --json state` in the same turn, exactly as you would quote a sha.
- **A pre-existing-gate red is triaged per owning file, but CHECK for a merged covering PR BEFORE filing per-file tickets.** When a lane reports a ratchet/gate red as "other lanes' product files", two turning-points bite in one pass: (1) the red often pre-exists the newest merge (verify at the pre-merge parent before blaming the newest PR), AND (2) the owning lane may ALREADY have the fix merged — the correction arrives alongside a merged PR that converts several files at once, so the per-file tickets you file are instantly moot and a dispatch on the split tickets races the merged fix. Measure before filing each ticket: `gh api repos/o/r/commits/<tip>/check-runs` for the ratchet rc, `git show <tip> --name-only` for which files the recent merge actually touched, and whether `linux/unit`/the gate finished green at that tip. If a merged PR already converted the file, CLOSE the per-file ticket citing that merge commit rather than dispatching it — a dispatch on a satisfied file burns a lane run and risks a race. Stand the dispatched lane down with a direct STOP message naming the merge sha that made it moot. The pipeline lane's own correction may itself arrive STALE (it described its PR as open/not-armed while the API showed it already merged at a different head) — always read `.state/.merged/.head.sha` from the API, never the lane's verbal status. A parent whose table shows merged children
  can still own an open follow-up; read its child/follow-up table before closing, or leave it open.
- **"Measured on main@<sha>" in a filed issue can be a PR branch.** A bot that measures from the checkout it
  happens to be sitting in files numbers for unmerged code. Before trusting any count: `gh api
  repos/<o>/<r>/commits/main --jq '.sha'`, then `git branch -r --contains <sha>` — a sha whose only home is
  `fork/<branch>` is that PR's head. Re-measure on main **without creating a worktree** (a worktree is debris
  you may not be allowed to clean up): `git grep -l '<pattern>' origin/main -- <path>`, `git show
  origin/main:<file> | wc -l`. An acceptance criterion quoting a wrong count is untickable, so correct it in a
  comment on the issue rather than in a chat reply.
- **A `success` bot run can be a decision with no artifact.** A triage leg returning `refine` (or `close`)
  posts a restated spec, adds the refined label, opens no branch and exits green — the issue is still nobody's.
  Read the verdict comment plus the branch list, not the run's colour, then re-dispatch it.
- **An issue whose premise is an alternative that `main` later ADOPTED is answered, not still-valid.** Some
  issues argue a choice was measured and rejected ("design X stays strict, do not relax it") and scope their
  acceptance on that basis. When a merged PR later took the other branch, every criterion quoting the rejected
  design is moot — the test the issue presupposes may not exist on the tree at all. Measure before trusting the
  body: `git merge-base --is-ancestor <adopting-pr-sha> origin/main` (it landed) and grep the live test/file for
  the symbol the issue names (gone ⇒ premise void). Record it as "answered by #<pr> — narrow to the residual or
  close" with the measurements, and say the rejected-design framing is historical; never leave it as scope to
  implement.

## In llgenie specifically

**The planner refines; it never implements.** Verdicts and rescoped bodies are the deliverable here, then the
work is handed to a bot: the in-repo CI bots by label/claim comment (`agent:implement` for issue-bot), or a host
profile via `message_agent` with the issue number, the verdict and the constraints. Check for a live
`bot-claim:` comment (TTL in the body) and an existing `agent/issue-<n>-*` branch BEFORE dispatching, or two
implementers race on one issue.

**Editing your own live-profile SOUL or SKILL is a versioned act, not a private edit.** A change to this
profile's behaviour counts only once it lands in the repo tree under `agents/<profile>/`: patch the live copy,
then file the `#791` versioning issue (six-section body, gated) whose PR copies the EXACT added text into
`agents/<profile>/skills/<skill>/SKILL.md`, and say in its claim that the live copy is ahead of tree and this
PR folds it live→tree. A live-only edit is a silent behavioural change with no diff for review — the precise
class #791 exists to stop — so never leave a self-skill patch unfiled. Verify the live patch landed before
filing: re-read the added region and confirm a distinctive substring of it is present (a large SKILL.md
overwrite can truncate), and quote that same substring in the versioning issue so the merge is checkable
byte-for-byte.

**Pick the host profile by work class, and read the roster instead of recalling it.** There are several llgenie
host profiles — implementer, pr-merge-conflict, architect, ci-pipelines-maintainer, documentation-maintainer,
engine-improver, security, pr-reviever — and the general implementer is the wrong destination for a rebase, a doc
rewrite or a pipeline edit even when it is the documented fallback. The ownership table and the loop-breaking
briefs live in the `llgenie-bot-orchestration` skill; treat that as the single source of truth so the two skills
do not drift.

**Label only what the queue can drain, and route the rest by hand.** An `agent:implement` label is a
promise that the CI bot will pick the issue up; when the implement leg is itself red, or the bot is capped
at a few runs a day, stamping every actionable issue builds a queue nothing drains and destroys the
priority order. Label the one issue the bot will reach next, send the single most valuable item to the host
implementer (no cron job, no cap), and deliver the ordered backlog as the queue itself. The brief is a
template: `templates/implementer-handoff.md` — issue number, verdict, the measured defect, the required
direction with its anti-goal, and the constraints that keep the result reviewable (fresh worktree off
`origin/main`, one ready-for-review PR with `closes #<n>`, gates through make, never merge, report the PR
URL).

**When you file or restate a body yourself**, the repo's shape gate makes this a writing task with traps: use the
repo's own renderer where one exists (`scripts/issue_body.py`'s six sections, `Technical` last). The EXACT
`SECTIONS` tuple (read it from the source, never guess from memory) is `Problem / Why it matters / How we fix it /
Benefit / Acceptance criteria / Technical` plus optional `Not covered` — do NOT brief lanes with a spoken list like
`Goal/Test/Evidence/Notes`; that is wrong and lanes must override it to the real tuple. The `Acceptance criteria`
section must contain a checkbox (`CHECKBOX`), and every other `##` heading inside a pasted document (a SOUL.md or
SKILL.md dropped into `## Technical`) must be demoted to one more `#` level — a top-level `## Technical` otherwise
parses as extra sections and displaces `Technical` from last (the shape gate `missing()` reds on `## ` headings
already given or unknown ones). Verify the body after the POST with the gate itself
(`scripts/issue_body.py missing() == OK`, `has_accept=True`), not by counting `[ ]` in the whole body (raw
`[ ]` count includes prose; what matters is `Acceptance criteria` present + tickable). `issue_body.py` is a
LIBRARY, not a CLI: `python3 scripts/issue_body.py check ..` reports nothing and exits 0 on ANY body (mine
did for a deliberately malformed control), which silently "passes" an un-shaped filing. Invoke it as a
function — `python3 -c 'import sys;sys.path.insert(0,"scripts");import issue_body as ib;print(ib.missing(open("b.md").read()))'`
— and run that against the LIVE body re-fetched from GitHub (`gh api repos/o/r/issues/<n> --jq .body`),
never a local copy overwritten by `gh issue view > file`, which degraded output can truncate. Filings that
invent their own headings (`## Goal`, `## Implementation route`) instead of the six-section tuple are
un-ready even when they read fine — re-gate every body you file BEFORE dispatch, and again after the POST. Verify with a
fence-aware scan — walk the lines tracking ``` parity and only count `^## ` outside a fence — because a bare
heading regex reports headings that a reader never sees, which is how you file a false complaint about someone
else's correctly-shaped issue. Mechanics and the self-reference check:
`references/filing-a-well-formed-issue.md`.

**Correcting a number in an issue body is an edit, not a comment.** When an expectation table or count was derived from a superseded head, the wrong figure is what the implementer reads; a retraction in a comment leaves it standing. So PATCH the body, state the measurement basis above the table (which head, which **entry point** — `script.py jobs --paths <probe>`, not "the classifier"), and prove no stale figure survives by grepping the body you just wrote:

```bash
gh issue view <n> --json body --jq .body > /tmp/b.md
grep -c '<the stale figure>\|<the stale phrase>' /tmp/b.md    # must be 0
wc -c < /tmp/b.md                                            # shape check: an issue body is KB, not bytes
```

Two tells that a table was measured at the wrong tree: every row is off by the same class (one filter matched more than intended, so several counts inflate together), and some rows are right — a uniform offset is one bad predicate, not many bad rows. Re-derive from the live head rather than adjusting the offsets.

At most one PR per issue, from a fresh worktree off `origin/main`; `make openspec-new NAME=<kebab>` runs
its CLI in the container as root, so `sudo chown -R $(id -un): $(id -gn) openspec/changes/<name>` before
writing `proposal.md` / `specs/<cap>/spec.md` / `tasks.md`, and every gate (`make test-unit`, `lint`,
`check-wiring`, `check-docs`, `check-workflows`, `openspec-validate`) runs through make. The PR goes to the
upstream base with the fork head (`--head <fork-owner>:<branch>`). Check `git remote -v` first: in the
standard agent checkout `origin` is the UPSTREAM and the fork is `fork`, so the push is
`git push -u fork <branch>` even though the repo's own docs write it as `origin`. Write the
`agent-wiki/` entry in the change commit and replace its `PR: _this branch_` placeholder with the real
number once the PR exists (`make check-docs` accepts an issue reference alone, so the placeholder passes
CI and is easy to leave behind). Repo depth for the engine/CI side, and the reactor/remotes/verification
detail: `references/bot-claim-and-branch-sweep.md` plus the repo's own `docs/BOTS.md`, which is the file
that has to stay true about which bot runs in which cron slot.
