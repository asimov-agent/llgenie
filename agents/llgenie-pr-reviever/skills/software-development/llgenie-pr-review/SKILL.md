---
name: llgenie-pr-review
description: "Use when reviewing llgenie PRs: evidence, gates, verdicts."
version: 1.26.0
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

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `llgenie-pr-review`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## Local verification depth

`references/local-verification.md` — the repo's own test venv and the `-s`/`-x` trap, golden/fixture
freshness (a golden can be in the PR diff *and* stale), measuring on the data path the test actually
uses, the control shape, and the clean-HOME split for profile gates. Read it before publishing a
local red **or** a local green as evidence.

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

A dispatch must name the PR **and the head sha to judge** (branches move under you), and the rule
is that a verdict cites the run id at that head. Verdicts are **comment-only by default**; a
`do-not-merge` is allowed only with a one-line reason *and* a one-line unblock condition in the same
comment, and lifting it is the planner's call. If the run at the head has no conclusion yet, say
"no verdict exists yet — run `<id>` is queued" and stop; never manufacture a verdict and never move
a head to produce a fresh run.

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

## The skill body has a size ceiling, and it fails silently

`skill_manage` refuses a save once `SKILL.md` passes roughly **100,000 characters**, and the refusal
reads `batch aborted, all touched skills rolled back`. A refused save looks like a save: the lesson
lands nowhere, or lands only in the duplicate profile copy — which is how a lane can appear to "keep
forgetting" lessons it keeps writing down. It is a mechanism, not a discipline problem.

Measured on this skill: **100,688 b** and every save refused; after moving the 628-line
`## Standing rules for this repo` section verbatim into
`references/standing-rules-for-this-repo.md` (pointer left at its heading), **41,498 b** and the save
succeeds. **A lesson recorded in the same edit that clears the cap is the only evidence the cap moved.**

So: when a lesson will not save, `wc -c SKILL.md` first. If it is near the ceiling, move the largest
self-contained section **verbatim** into `references/`, leave a one-line pointer, then verify with a
line-by-line `missing: 0` check — never eyeball a split, and never split by concatenation.

**Verify a split by grepping for the rules that must STAY, not by reading the pointer you wrote.**
A split moves whatever you selected, and the section boundaries do not know which sentences were
load-bearing. The check is mechanical and it fails in the direction you least expect:

```bash
for p in 'does not approve and does not merge' 'No squash, no auto-merge' 'working on #' 'REVIEW_REQUIRED';
  do printf '%-40s ' "$p"; grep -ci "$p" SKILL.md; done     # every count must be >= 1
```

Measured: after moving a 628-line rules section out, the lane that wrote the acceptance criterion
("never-approve/never-merge stays in the body") still had `grep -ci 'never approve' → 0` — the rule
survived only in the reference, behind the hop the acceptance existed to forbid. **An acceptance you
authored is not evidence you met it**; grep the body for the sentence, and if it moved, put it back
above the pointer. The pointer should name what is behind it, never carry the only copy of the rule a
review cannot start without.

## Standing rules for this repo (they override generic review habits)

**The one rule that must never need a second lookup: this lane does not approve and does not merge.**
No squash, no auto-merge, no `gh pr merge`, no approval review — `reviewDecision` stays
`REVIEW_REQUIRED` on everything this lane touches, and a green PR is handed off in one line to the lane
that owns it. `agents/manifest.json` declares `never-merge` for this profile, and rule 16's carve-out
applies: report `auto=none (lane owner instruction)` and name where that instruction lives.

The rest of the standing rules live in
**`references/standing-rules-for-this-repo.md`** — 628 lines covering the author gate, hold discipline,
push and rebase behaviour, and the CI-read rules. Load it before acting on any of those; the always-on
summary a review needs without a second lookup is below in `## What actually blocks a PR`,
`## Verdicts` and the evidence block.

## Fleet rules 13–16, verbatim (from #873's body at commit time — do not paraphrase when citing)

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
git -C /home/asimov/repository/git/llgenie fetch origin pull/<n>/head
git -C /home/asimov/repository/git/llgenie-wt/<name> status -sb   # reuse an existing tree if present
# else: git -C /home/asimov/repository/git/llgenie worktree add --detach ../llgenie-wt/pr<n> <sha>
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

## Repo gates that a change must satisfy (pick per diff)

`ci-unit` chain in `Makefile`: `skills-validate` → `check-engine-skill-gap` →
`check-engine-params` → `check-engine-coverage` → `check-engine-source` → `check-wiring` →
`check-secret-output` → `check-docs` → … plus `openspec` (Linux **and** macOS) and
`check-pr-authors`/`check-pr-hygiene`. A new user-facing make target needs, in order:
`.PHONY`, a `DEFERRED` entry in `scripts/issue_bot_gates.py` (never `FAST_GATES` — its
membership is a contract asserted by a test), a mention in `README.md` or a linked
`docs/` page (`check-docs`), and a truthful "CI" help line (`check-wiring`). Every
`openspec/changes/<name>/tasks.md` box must be ticked in the code commit.
See `containerized-repo-verification/references/llgenie-engine-pipeline.md` for the
engine → image chain and `worktree-branch-hygiene/references/llgenie-repo-notes.md` for
the gate order and flakes that are not the author's. For keeping a verdict tied to a real base —
rebasing off a squash-merged ancestor, and re-verifying your findings on the merged sha — see
`references/base-and-merge-integrity.md`.

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
  its `[check-docs] ok: …` line) because that is the gate the change must pass. Say plainly which
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
- **Prove where a red comes from before you attribute it to the PR: reproduce it on `origin/main`.**
  A board can show five red PRs that share one broken default branch, and holding each of them parks
  work for a defect it does not carry. Check `main`'s last run first, then reproduce:
  ```bash
  git -C /home/asimov/repository/git/llgenie worktree add --force --detach ../llgenie-wt/vmain origin/main
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
- **Check that a fix issue's acceptance command is the command CI actually runs.** An issue scoped to
  one module (`pytest tests/test_x.py -q`) can be satisfied while `make ci-unit` stays red — so every
  PR remains unmergeable and the lane has spent a push for nothing. Add the widening as a comment on
  the issue (all failing modules, then `make ci-unit` exit 0, then a completed `linux / unit` run quoted
  with its id) rather than silently reviewing against a criterion that cannot close the gate.
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
- **`gh run list --commit <sha>` lags a fresh push; the API does not.** Minutes after a push it can
  report no runs for a sha that already has three, which reads as "CI never triggered" and invites a
  bogus empty commit. Ask the API instead:
  `gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>&per_page=10" --jq '.total_count, [.workflow_runs[]|"\(.id) \(.name) \(.status)/\(.conclusion)"]'`.
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
  note-less fragment behind.
- **When your local branch has diverged from the fork ref you mean to update, push to a DISTINCT branch
  — never force over a shared/foreign branch lineage.** A reviewer's record commits often build on
  `main`'s history while the fork branch (`fix/…`, `reports/…`) still carries the earlier review-record
  lineage, so `git push fork <branch>` is rejected non-fast-forward and `--force` would discard the
  remote lineage. The safe move is `git branch <new-name> HEAD && git push fork <new-name>` — a fresh
  ref that carries your commit without rewriting anyone else's — then verify with
  `git ls-remote fork refs/heads/<new-name>`. Confirm ancestry first (`git merge-base --is-ancestor
  <remote-sha> HEAD`); if it is NOT an ancestor, they diverged and a force is the wrong tool.
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

- **Request changes / block** — a factual claim in the diff or body is false (stale census,
  a gate that does not do what it says), a gate is red for a reason the diff caused, the
  diff is out of scope, or secrets/permissions weaken.
- **Comment** — everything verified green with only non-blocking notes (doc omissions,
  nits, merge-order advice). State exactly what you ran and what it returned.
- **Nothing** — a PR whose head sha, checks and review state you already reported and that
  has not changed.

**A verdict is about a sha, so it expires; a cause is not, so post that once on the umbrella.**
When every head in a family has moved past the shas you read, do not post a late verdict dressed as a
review — freeze one head and judge it, or say nothing. What does not expire is the shape of the failure:
"these branches are short one index note against `main`'s count, merge-base `<sha>`, remedy is a rebase"
is true of any head that kept that base, so it belongs on the tracking issue and each lane can act on it
without a fresh measurement from you. Post the cause on the umbrella issue, the verdict on the PR, and
never the other way round.

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
own issue and leave the PR alone, rather than approving it yourself to unblock the queue (nobody here
may approve). Equally, never derive "green" from a job count that is still moving: a run with rows
queued or in progress has no verdict, and the pending row is often the deciding one.

## Evidence block to include in every review

Numbers and exit codes, from your own run: the gate command + exit code, the failing or
absent engine/cell names, the test count, the doc gate line (`[check-docs] ok: …`), and the
CI verdict with the run id. Quote `gh` output, never paraphrase "CI looks green".

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
