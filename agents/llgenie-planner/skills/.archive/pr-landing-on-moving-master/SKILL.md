---
name: pr-landing-on-moving-master
description: "Use when landing PRs on an auto-merge queue or a red PR."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github-actions, pr, rebase, merge-queue, openspec]
    related_skills: [containerized-ci-pipeline, git-maintenance]
---

# Landing PRs on a moving master (auto-merge queue)

## When to Use

Use when a bot pipeline + `auto-merge` keeps master moving under you — rebasing
several open PRs, resolving their conflicts, updating PR/issue bodies, and keeping the
squash queue green without ever merging yourself. ALSO the entry point for "fix this red PR"
and "solve this PR": the triage for a failing job (which STEP failed, whether the gate is red
on the base too, the local store the branch does not carry, a live-source gate) is in "CI red
but `make test-unit` green locally" below.

A repo with a bot-pipeline + `auto-merge` (squash + delete-branch) and a GENERATED
OpenSpec index lands PRs constantly, so master moves several times a session, every
merge re-stales the generated index and re-conflicts the remaining PRs, and each
PR must stay a single squashable commit. This is the workflow that keeps the queue
moving. ALWAYS read the `pr-closure` guard's rule FIRST — it decides whether a PR body
may close its issue, and getting it backwards reddens a merge.

## The pr-closure guard / the branch-name rule that decides every body edit

The guard is REPO-SPECIFIC: `scripts/pr_closure.py` may not exist in the repo you are in
(it errors `No such file or directory`). Detect it before assuming the exact command; the
RULE it encodes is universal and you enforce it either through the script or the API:

- **Branch name ends in a number** → it implements that issue → the body MUST carry a
  closing keyword bound to it. Strip its `Closes #N` and the guard refuses.
- **Branch name carries NO number** → it implements no issue → the body MUST NOT close
  anything; it would close an issue it does not implement. Replace `Closes #N` with
  `Refs #N` so the issue is closed by hand on merge.

When the script is absent, verify the invariant from GitHub itself:
`gh pr view <N> --json closingIssuesReferences` must be empty for a numberless branch
(or must name the issue for a numbered one). Run the check on (branch, body) before
editing or publishing ANY PR body — it is the arbiter and catches BOTH directions of
mistake. Do not "fix" bodies of a whole batch the same way: the two cases need OPPOSITE
edits. Read what the branch NAME resolves to, not what you assume.

**Run the guard on the (branch, body) PAIR before `gh pr create` — a head branch cannot be
renamed.** GitHub has no "change the head branch of an open PR" operation: `gh pr edit`
touches the title/body/base, never the head, and deleting the old head CLOSES the PR. So a
branch that encodes no issue (or the wrong one) cannot be repaired in place — the PR opened
from it goes red on the closure guard with "implements no issue, so it must not close one"
even though every other gate is green. The cheap order: cut the branch as
`<prefix>/<topic>-<issue>` from the start, compose the body with the repo's own composer
(`make pr-body ISSUE=<n>`), dry-run the guard against that pair, and only then open the PR.
When you find out afterwards: push the SAME commit under a correctly-named branch, open the
new PR from it, and close the old one with a one-line comment naming the guard as the reason
(and say so in the report — a closed PR that reads like a failure is worse than a renamed
branch). Verify the new head with `gh pr view <n> --json isDraft,mergeable` before walking
away.

## When the rule forbids force-push: merge master and take YOUR side of the conflict

Some repo rules refuse force-pushing a bot/residue branch ("resume, never
force-push"). When master has SQUASH-MERGED your own earlier work into one
commit, a follow-up branch cut from the pre-merge base now conflicts with
master on every file that work touched — file-by-file against itself.
Resolution that respects the no-force-push rule:

1. `git fetch origin master && git merge origin/master --no-edit`.
2. For each conflicted file inspect both sides: master's is a squash of the
   same content; your branch's is a SUPERSET (you extended it this change).
   Resolve with `git checkout --ours <file>` and `git add` — lossless, since
   master carries nothing your side does not, plus the squash.
   Proof-check the superset survived the outcome: grep your additions on the
   resolved files (`grep -c "<your new symbol/string>" <file>`).
3. Regenerate any GENERATED index (e.g. `make openspec-index`) and re-run the
   fast gates — the merge commit is kept, NOT squashed away, and it does NOT
   need reverting.
4. A normal `git push` (no `--force-with-lease`) is then safe — the branch is a
   merge-up to date.

Only fall back to `git checkout --ours` when you have actually confirmed your
side is a strict superset; a genuinely divergent conflict needs a hand-merged
union, not a blind "ours".

## Rebase sequence (one PR per worktree)

1. `git fetch origin`; each rebase runs in its OWN worktree cut from `refs/remotes/origin/master`
   (this repo's rule — never move the caller's checkout, base verified not assumed).
   **The repo's base seam asserts the CALLER's checkout, not your worktree.** Invoked from the main
   clone, `make base-rebase BRANCH=<b>` refuses on any uncommitted/untracked path there
   (`REFUSED: the tree has uncommitted changes, so a rebase would move work it cannot see`) even when
   that path is nowhere near the branch — and it does not rebase anything. Read the path it names: if
   it is not in the worktree, run the rebase where the branch actually lives
   (`git rebase origin/master` inside the worktree) instead of "cleaning" the user's checkout, and
   leave the seam to the CI job that owns it.
2. `git rebase origin/master`.
3. Conflicts are usually UNION, not either/or: the Makefile `_test` chain appends test
   files, so master's newly-added test AND the branch's must BOTH survive — taking either
   side silently drops the other's test and ship something unguarded. After auto-resolve, grep
   for `<<<<<<<` markers and diff-check that the branch's distinct content survived. For a
   test-file-list conflict, PROVE the union lossless instead of eyeballing it: parse both
   sides' file lists and assert `set(master) | set(mine) == set(merged)` —   a naive
   resolution drops the other side's newly-added test file (e.g. master's new
   `tests/test_<feature>.py`) and the assertion is the only thing that catches it.

   Two traps make the conflict-time proof insufficient; re-check the FINAL tree after the
   whole rebase finishes, not just the conflicted commit:

   - **The list line can exist in MORE than one copy** (a prior auto-merge/homegrown edit
     duplicated the recipe line), and your single edit may land on one copy, leaving a
     stale second copy that names a test file missing from the tree. When the anchor's
     search string occurs more than once, stop and enumerate the occurrences before
     replacing; and after the rebase, grep the RESULT for the other side's test names with
     `os.path.exists()` on each file — every name must name a real file.
   - **A LATER commit in the branch's own history can re-drop the union.** The branch
     often carries a follow-up commit that re-touches the same recipe line from its
     pre-rebase (pre-merge) copy, silently reverting the just-union'd list and losing
     master's newly-added test again. So after the full rebase, grep the final Makefile
     Makefile for master's new test name (e.g. one main added after the branch forked) and re-add
     it if the later commit dropped it — a step that appears 'already correct at the
     conflicted commit' but is wrong at the branch tip.
     - **Unioning a line-continuation list folds the `\` into the names.** A Makefile
       conflict is often a `.PHONY` / continuation block (`foo \` newline `bar \`). When you
       `.split()` each side and union the tokens, the trailing line-continuation backslash is
       LINE TEXT, not a separator, so the merged list ends up carrying a stray `\` as a
       "target" (`agent-fetch search-smoke \ require-env \`). Strip the backslashes from each
       source line before splitting, and after the merge grep the line for a lone `\` between
       names — a bare `make -n help` / `make -n <target>` parse is the cheap check that the
       block still parses.
4. Regenerate the GENERATED OpenSpec index after EVERY rebase — but ONLY in the repo
   that has one: grep for the `openspec-index` target and an `OPENSPEC.md`. A repo with
   an `openspec/` dir but NO committed index (only `changes/`, `config.yaml`, specs)
   has nothing to regenerate — running the step there is a no-op that only wastes a
   search. In that repo substitute its real openspec gates
   (`make openspec-validate NAME=<change>`, `make openspec-tasks-check`). Where the
   index does exist: never hand-edit it, the commit count drifts on every merge and
   reds `validate`, and it resolves most index conflicts by itself.
   **A conflicted generated file: keep the BASE side, then regenerate.** Never
   hand-merge the `<<<<<<<` block of a file whose whole content is derived — the
   row/count deltas are meaningless individually. Take the base side (strip the
   markers keeping `HEAD`, or `git show origin/master:<index> > <index>`), run
   `make openspec-index`, `git add` it and continue the rebase: the generator
   reproduces every row from what is on disk, so the result is right by
   construction and cannot carry one side's stale count. Amend into the
   single commit (`git commit --amend`) so the branch stays one squashable commit.
5. Fast gates first (`make lint`, `openspec-check`, `architecture-check`) — they catch the
   generated/stale-index cases quickly; then the key test suites in the test CONTAINER via
   make` targets (a direct `docker run` does NOT mount the repo's git common dir, so git-
   dependent tests fail with worktree errors even when they pass under `make`). To run a
   few affected tests by hand in the container you MUST mount BOTH the worktree AND the
   parent repo it was cut from (`-v <worktree>:/repo:rw -v <parent>:/repo-parent:rw`),
   because the worktree's `.git` is a FILE pointing at the parent's common dir; mount only
   the worktree and git-dependent tests die on a missing repo. Keep the Makefile's flags
   (uid/gid, HOME=/root, stub auth paths) so the environment matches CI.
   **Mount the common dir at the SAME absolute path (`-v "$(git rev-parse --git-common-dir)":<that
   same path>`) and never at a remapped path with `GIT_COMMON_DIR=<other>`.** Tests that build
   their own git fixtures then resolve the REAL config through the remapped variable and
   `git remote add origin /tmp/...` lands in YOUR clone's config — measured: a hand-run suite
   left the checkout's `origin` pointing at a `/tmp` scratch remote (repaired with
   `git remote set-url origin <real url>`). When in doubt, run `make test` itself: it wires the
   mounts correctly, and a red CI is cheaper than a broken checkout.
6. `git push --force-with-lease origin HEAD`.
7. Re-run the `pr-closure` guard on the (branch, body) BEFORE the push lands — a rebase
   does not change the body, so this is a cheap re-confirmation that the amend did not
   drop the closing keyword and the branch still closes what it claims. If the guard
   refuses, fix the body FIRST, then push.

## Your user approves every merge — hold the queue DELIBERATELY, and say so

Where the user requires approving each merge (and forbids auto-merge) but the base repo's `auto-merge`
job squash-merges any green, conflict-free PR, the deliverable is a REVIEWABLE PR plus the repo's
documented human hold: `gh pr edit <N> --repo <o>/<r> --add-label do-not-merge`, applied BEFORE the
last check goes green so the land never races you (CI prints the hold and exits 0 — it is never a red
run). Then state the hold and its one-command release in the report
(`--remove-label do-not-merge`). A label the user did not ask for and cannot see the reason for reads
as sabotage, and the first thing you will be asked is "why does this PR have a do-not-merge label?" —
the label is a HOLD, not a review finding, and it is never an excuse to merge the PR yourself in
either direction.

**The hold belongs in the SAME message that first reports the PR**: the URL, the label, one clause on
why it is there, and the exact command that releases it. Announcing a PR without its hold, and
explaining only when asked, reads as a defect — the user cannot tell whether you mislabelled it or
intended it, and the first thing you spend the next turn on is defending a decision that should have
been one line up front.

## A rebase stops twice for non-conflict reasons: the commit EDITOR and a whole-file rewrite

Two rebase stalls look like a hang and are neither a conflict nor a slow test:

- **`git rebase --continue` opens the commit editor**, and a tool call that inherits an
  interactive editor waits until its timeout with the rebase half-finished (the tree looks staged,
  `HEAD` is still the base). Always continue non-interactively:
  `GIT_EDITOR=true git -c core.editor=true rebase --continue`. Same for `git commit` in a scripted
  flow.
- **A branch that REPLACES a file wholesale conflicts on every rebase**, forever, even though your
  version is the intended one: the base keeps editing the old file (a bumped pin, a new
  paragraph) and every base edit is a conflict against your rewrite. Resolve by taking your
  version (`git checkout --theirs <path>` while rebasing your own commit) and then REPLAYING the
  base's post-fork edits: `git diff <old-base> origin/main -- <old-path>` lists exactly the hunks
  that landed while you were open; transplant each into whichever new file now owns that content
  (a split rewrote the map, so the hunk's destination is usually a new reference doc). Skipping
  the replay ships moved text older than the base — and it is invisible to the conflict, because
  your side "won".
- **After the rebase, re-run the gates the branch itself added.** A generated index/validator that
  enumerates files on disk is DESIGNED to redden when the base adds one; that failure is the
  feature, so add the missing row/fixture rather than loosening the check.

## A "just rebase" ask is answered by the PUSH — never block it on the full suite

When the user asks to rebase an open PR, the deliverable is a pushed, `MERGEABLE` head —
not a locally-green full suite. Run the FAST gates to prove the conflict resolution lost
nothing (`make lint`, `openspec-validate NAME=<change>`, `check-wiring`, `check-docs`,
`check-workflows`, plus the make-target diff `set(origin/main) | set(mine) == set(merged)`),then `git push --force-with-lease <fork> HEAD:<branch>` and read back `headRefOid` +
`mergeable` == `MERGEABLE`. Do NOT start `make test-unit` / `make loop` and hold the push
until they finish, and do NOT poll a background verification process before pushing — the
whole suite runs as CI on the PR anyway, so waiting on it only makes the push late. The
push IS the rebase; the full suite is CI's job, confirmed afterwards with `gh pr checks`.

**Respect the caller's squash preference — a rebase keeps the branch's commits.** When the user asks to rebase several PRs and "see the changes", preserve every authored commit on each branch (2-3 commits stay 2-3, rebased); do NOT squash them into one. Squashing is a separate explicit request (usually a dedicated pr-finalization pass on an approved PR) — never fold it into a batch rebase, and never use `-i`/`reset --soft` to collapse history the user is rebasing so they can review it. After the rebase, report the per-branch commit count (`git log --oneline origin/main..HEAD`) so the user can confirm nothing was lost.

## Verify the ask is still live before acting on it (stale-plan trap)

On a fast auto-merge queue, a request to "fix PR <N>" or "work the issue behind
<N>" can already be obsolete: a later PR may have merged and resolved it.
Before creating a worktree, opening a change, or proposing a plan, re-fetch
`origin/master` and read back the CURRENT state of every number the request names:

- `gh pr view <N> --json state,mergedAt,mergeCommit` — an already-MERGED PR with
  a squash commit on master means "fix the PR" is a no-op.
- `gh issue view <N> --json state,stateReason` — a CLOSED/COMPLETED issue means a
  follow-up already landed it (its "Not covered" items are each their own issue, and
  a later merge may have closed them too).
- For each issue the plan names, check whether a merged commit since the request
  resolved it: `git log --oneline origin/master -N` near the merge tip, or `gh pr
  view <N> --json closingIssuesReferences`.

The cost of skipping this is planning and opening work on a task the queue already
finished. When the original numbers are all resolved, say so plainly and re-derive
"next" from the CURRENT open PRs (`gh pr list --state open` + their
`mergeStateStatus`) and open issues — not from the request's framing.

## Refining a batch of open issues: re-measure, judge, then comment — not blindly implement

When asked to "go over the open issues/PRs, rebase them, fix them if they still make sense, otherwise skip and comment, analyze and refine", the deliverable is a JUDGED, re-scoped queue — not a pile of new implementations. Do it in this order:

1. **Re-measure every number against CURRENT master, not the request's framing.** `gh pr list --state open` + `gh issue list --state open`; for each, read back state and whether a merged commit since the request already resolved it. A PR that is `at/after master` needs NO rebase — say so and move on. A merged PR whose issue is still open is a closure gap: close it by hand (the PR deliberately used `Refs #N` because its branch name carries no number, so the `pr-closure` guard forbade a closing keyword — hand-closing on merge is the intended step).
2. **Classify each open issue as RED (currently failing) vs LATENT (mechanism intact, symptom absent).** A recurring failure that stopped only because a human PR happened to regenerate the file is a REPAIR, not a prevention path — the recurrence is latent, not fixed. Do not mark it closed or "done" just because master is green; the "Done when" is unmet. State the old verdict and the new one in separate sentences, each with its evidence.
3. **Consolidate issues that share a root cause before refining them.** Two issues that both describe "verification runs against the PR's own tree, never the merge result" are ONE defect with two faces — refine them together and say so, rather than treating each as independent. When one issue's facet is another issue's whole subject (e.g. a shared-registry issue whose generated-file facet IS the post-merge-authority issue), narrow the first to what is left and point the rest at the second. This keeps the queue from carrying N copies of the same root cause.
4. **Post a sharpened scope comment per issue** (via `--body-file`, never inline `--body`): status (valid/latent/narrowed), the re-measured evidence, why the "Done when" is or is not met, and a refined "Done when". A comment that only says "still valid" adds nothing; the value is the re-scope.
5. **Only implement what genuinely remains and is unblocked.** A facet that is blocked by coupling (e.g. a Makefile chain whose replacement turns the suite red because 16 test files self-assert their presence) is its own issue, not something to force through this pass.

## Check scheduled-bot failures on master, not just push runs

`gh pr checks` and the latest push run can all be green while a SCHEDULED bot job
sits red on the same branch — it fires on cron, never on a push, so it is invisible
to the health checks that watch push runs. Sweep `gh run list --branch master`
across ALL events (`--json workflowName,event,conclusion`) and flag any
`schedule`/`workflow_dispatch` run with a `failure` conclusion even when the latest
push run is green. A red bot is unowned work on the live branch.

## Confirm the landing — do not assume the merge succeeded

After `auto-merge` reports green, read back the OUTCOME, never trust "CI green"
→ "it will merge". Three read-backs, all against the fetched refs:

- `gh pr view <n> --json state,mergeable,mergeStateStatus` → `state == MERGED`
  (a PR can sit `MERGEABLE` with all checks green for minutes while the squash job
  queues, or fail the squash halfway);
- `gh issue view <n> --json state,stateReason` → `CLOSED/COMPLETED` for the issue the
  PR's branch name implements — a merged PR can still leave the issue open if the body's
  closing keyword was stripped in an amend;
- `git fetch origin && git show origin/master:<file>` → the change is actually on the
  landed head, and `git rev-parse --short origin/master` matches the squash commit.

The read-back also catches the moving-master trap where the PR you pushed a minute ago
was already the merge target and is now in master — re-list the queue before starting
anything.

**Audit the merged paragraph, not just the diff.** A partial doc/prose edit ships a contradiction: the
paragraph's opening sentence still says the query set is *one per model* while the sentence added two
lines below says *two per model*, and a hard-coded figure (`today: 1 of 10`) keeps a value the gate now
prints as `2/10`. Each hunk looks fine on its own in review, so the defect survives a green merge. After
a prose change lands, `git show origin/master:<file>` the WHOLE section and (1) grep for the old quantity
word (`one`, `single`, `only`, a literal count) beside the new one, and (2) run the target that PRINTS the
number (`make <report-target>`) and diff its output against every literal in the prose. Fix it on a fresh
branch cut from the fetched base as a small follow-up PR that implements no issue (numberless branch name,
no closing keyword); a stale literal is a defect whether or not a gate reads it.

**A number a PR body states must come from THAT PR's own run.** Copying a count out of a local
`make test-unit` or a sibling stacked branch writes a false measurement into a reviewed document —
the local run measures a different tree. When the body claims `N passed`, read it back from the PR's
own job:

```bash
gh pr checks <N> --json name,link -q '.[] | select(.name=="linux / unit") | .link'  # …/runs/<run>/job/<job>
gh run view <run> --job <job> --log | grep -E '[0-9]+ passed'
```

Correct the body with `gh pr edit <N> --body-file <file>` rather than leaving a number nobody can
reproduce.

### A commit pushed AFTER the merge is orphaned — land it as its own PR

The auto-merge job matches the head SHA its run validated, so a documentation/comment commit pushed
while the run is in flight is not in the squash commit even though the PR reads `MERGED`. Compare
before claiming the branch landed: `gh pr view <N> --json state,headRefOid` against
`git log --oneline origin/main -1` and `git ls-tree -r origin/main -- <your files>`; a `MERGED` PR whose
`headRefOid` differs from what you have locally means your last commit went nowhere.

Do not force-push or reopen the merged PR. Cut a NEW branch off the fetched base, cherry-pick the
orphan (`git switch -c fix/<kebab> origin/main && git cherry-pick <sha>`), push to the FORK, and open a
small PR whose `Issue:` names the already-merged PR and states the defect in the landed file — no
closing keyword if the issue it relates to is already closed. Say plainly in the report that the first
PR landed at an older head and the correction follows separately.

### Merged-green is not fix-verified — re-dispatch after the merge

Confirming the LANDING (above) proves the change is on master, not that it WORKS in
production. After a fix auto-merges, re-run the bot through its own
`workflow_dispatch` (dry/read-only form where one exists), read the run log for the
CONCRETE behavior change, and only then call it verified. In particular a check gated on
a credential the run rarely has (e.g. `gh secret list` needs repo ADMIN; the default
token 403s) is SKIPPED silently — every run stays green while that check never
executes — so a green run is NOT proof the check ran; read the log for the skip/WARNING
line, and fix such a check to run against an in-repo declared contract instead of the
admin-gated live read. Do one bot per pass; verify each before starting the next.
Details: `containerized-ci-pipeline` → `references/verification-discipline.md`.

## Read a file from a ref WITHOUT touching the clone you must leave alone

`git show <ref>:<path>` reads a file from a ref to stdout and leaves the working tree
and index untouched — the only safe way to inspect master content mid-work in a clone
you must not modify. NEVER use `git checkout <ref> -- <path>` for inspection: it writes
the file into the working tree AND stages it, silently dirtying the caller's checkout
(`M ` in `git status`) — and the form even looks like a read, so it is the exact
command that trips a "verify the guard landed on master" inspection step.
Recovery when you already ran it: `git restore --staged <path> && git checkout --
<path>` — the plain `git checkout -- <path>` alone does NOT undo a STAGED write;
restoring the index first is the step that releases it. Confirm `git status` is back to the exact pre-touch state (only the
pre-existing untracked files remain) before continuing.

## When a rebase onto main reddens the branch's OWN new guard — main merged a violator

A rebase can surface a failure in the branch's OWN freshly-added test, not in the base.
When main, since the branch forked, merged a sibling PR that introduced NEW code (a new
make target, a new leg, a new step) that the branch's new invariant test governs, the
validation now scans the merged tree and flags the sibling's code as a violation — the
branch's own test that exists precisely to stop that violation is the thing going red.

- This is the guard WORKING, not a defect. `1 failed, <thousands> passed` where the
  assert names a target/step main just added is the roster-deriving validator doing its
  job, not a regression in the branch.
- Fix the MERGED side into compliance: add the missing guard/line to the newly-merged
  target exactly as the branch's rule demands (e.g. a leg that starts the agent image now
  must run the pre-flight key guard too). Add it as its OWN separate Conventional Commit —
  do NOT amend it into the branch's original feature commit (a reviewer must see the
  parent-merge integration apart from the feature), and do NOT loosen or annotate the
  test — a validator that derives its roster from the repo rather than a hardcoded list is
  exactly what caught it; annotating it would defeat the mechanism.
- A validator with a derived roster catches siblings merged WHILE the change was open;
  hardcoded validator lists miss them, which is the stronger reason to derive.
- Re-run just that validator in the test container (`make test-unit` for the one file), and
  note in the report that the file-derived roster is what caught the merged-tree gap — a
  loop run will confirm it later.

## Master can itself run RED — that blocks the ENTIRE queue, not just a PR

A generated-index drift reds `validate` on master, and then every open PR sits red too.
Before chasing individual PRs, check `gh run list --branch master` and the latest
`validate` conclusion. A tiny PR that just regenerates the index unblocks every PR at
once — it is the highest-leverage action in the queue.

### A live-source generated artifact is red on the BASE: regenerate it, probe what it drops, file the gate's own defect

A committed artifact rendered from a live external search (a quant/link catalog, a coverage table, a
price list) turns the shared gate red on the base whenever the live source stops returning an entry the
file records — so EVERY PR sits red for a reason none of them caused, and the PR's own suite is already
green (`N passed`). Do not chase it as a test failure and do not hand-prune the artifact:

1. **Prove it is base drift, not flake.** Run the gate twice or three times against the base
   (`git worktree add --detach ../wt-base origin/<base> && make check-<artifact>`): a stable failure is
   upstream drift; an intermittent one is the gate reading a rate-limited/live call and is a different
   defect.
2. **Read the generator's `check`/`compare` code first.** It decides what is a FAILURE (a committed row
   the generation no longer produces) versus a NOTE (reordering, a new row). That tells you whether a
   full regeneration is required or whether the committed row is simply dead.
3. **Run the repo's generator target** (`make sync-<artifact>`) — never edit the artifact by hand, and
   never trim only the failing rows so the check goes quiet: the generator is the sanctioned path and
   the next run would diff it anyway.
4. **Probe every entry the regeneration REMOVES before accepting it.** The check compares
executable-side direction only (`committed ⊆ generated`), so a sync that silently drops a still-live
entry stays green and the product stops offering it. `curl -s -o /dev/null -w '%{http_code}' <api url>`:
   `200` = still public, its loss is the gate's bug (keep it, report it); `401/403` = gated, correct to
   drop; `404/410` = genuinely gone, correct to drop.
5. **Re-run the check twice after regenerating** — a passing check immediately after a sync proves the
   artifact matches that moment's live read, nothing more; a second run is the cheap stability test.
6. **Commit the artifact as a data refresh, on its own commit, with the measured cause in the message**
   (which entries went, why each is gone, the numbers the gate now prints). Its diff is large only
   because the render re-records the live ordering — say so rather than letting a reviewer hunt for the
   semantic change.
7. **File the gate's own defect as its own issue** (the live-search churn turning the shared gate red,
   and a sync dropping a still-live entry), link PR ↔ issue both ways, and name it in the PR body's
   `Not covered`. The data commit clears today's red; it does not fix the mechanism.
8. **Record the refresh in the change's dated note** so the PR's file list and its note agree — a data
   artifact appearing in a feature PR without a word reads as an unrelated drive-by.

### Regenerating a hand-edited generated count is a symptom loop, not a fix

Repeatedly `make openspec-index`-regenerating around merges is whack-a-mole: if the
generated artifact's only failure is a COUNT every committed change must bump to match,
each merge re-stales it and a regeneration goes stale again within minutes — the queue
never stops touching it. When that is the shape (index README whose sole complaint is
`Active changes: N` vs `N+1`), stop regenerating and make the check COMPUTE the value at
validation time (count changes on disk / in git) instead of reading a committed number
that every change must hand-edit. Treat the symptom-once routing as an UNBLOCK, and the
check-time computation as the root-cause fix a follow-up should land.

When you DO report progress on this class of work, separate the two states explicitly:
state plainly that the ORIGINALLY-REPORTED failure is fixed/closed/not-active, AND
state separately that a DIFFERENT failure is now red if one is. The user may keep asking
"is it not valid anymore or active?" when a single report blurs "the thing I asked about"
with "whatever is currently red" into one sentence. Name the old verdict and the new one
in separate sentences, each with its evidence.

## Auto-merge churn: re-rebase each merge

`auto-merge` merges in the background. Every merge moves master → re-stales the index →
re-conflicts the PRs that touched the same files. After each merge, re-fetch, re-rebase the
remaining PRs onto the NEW master, resolve (index regenerates; Makefile/workflow are unions),
re-run the gates, re-push. A PR that was the merge target itself is now in master, not open.

**With THREE or more of your own PRs open, repair them ONE at a time, not all after every
merge.** Preparing all of them is N×(merge + regenerate + push) and each push restarts a
~15-minute validation that the NEXT merge re-stales again — the queue then costs N² and no PR
ever lands, because every push invalidates every sibling. Fix the one at the head of the queue,
wait for it to merge, then re-fetch and prepare the next. A four-PR batch prepared together
governs nothing: the first merge reds the other three on the same generated file.

## Two of your OWN additive PRs can conflict on the same source file — keep BOTH features

When you have two of your own PRs open that both touch the same non-generated source file
(e.g. two validators both editing `scripts/check_<thing>.py` + its test file), the FIRST
re-merge is clean but the SECOND turns `auto-merge=FAILURE` / `mergeable=CONFLICTING` the
moment the first lands — a signal to clear it with merge+union+push, never to recreate the
PR. The two sides are ADDITIVE: each PR added its own distinct feature to the same file, so
the whole file is the union, not either/or. Taking `--ours` or `--theirs` silently drops the
OTHER PR's feature while the file parity you are also pulling keeps the failing/reporting
half of both — under-guarded exactly where both wanted guards.

- `git merge --no-edit origin/master`; the conflicted regions are usually pure appends (new
  test functions, new `main()` call-list lines, new rule-registration blocks). Resolve them
  programmatically keeping BOTH sides in every hunk, not one side per hunk:
  `re.compile(r"<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> origin/master\n", re.S).subn(lambda m: m.group(1) + m.group(2), s)`
  over each conflicted file. Do not hand-edit `=======` regions — a stray marker left behind
  is invisible to git (the file is "resolved") and only a syntax run catches it.
- Then PROVE both features survived the union, not just that the file parses: grep each
  side's NEW symbol on the resolved file, and run the file's own self-test
  (`python3 tests/<file>.py` → `PASSED N | FAILED 0`) — a passing count is the lossless
  proof, the same way the Makefile list-union assertion is. If both validators exist and
  both report (e.g. `909 files scanned` with the widened set AND the derived-name guard
  list), both sides are live.
- **Two of your own PRs both PREPEND a row to an append-only index** (`CHANGES.md`, a changelog, a
  participants table): the second one conflicts on the table's first line even though both edits are pure
  additions. Keep BOTH rows, newest first, and delete nothing — a union that drops one row silently
  unindexes a merged change and the docs gate reds on the note nobody references. Your own row also
  usually cites only the issue (`| #694 |`) because the PR did not exist when it was written: after the
  PR is opened, a follow-up commit updates it to `| #694, #699 |` and adds the PR number to the wiki
  note's header — the note and the index row must name both, and that follow-up is a normal commit on
  the open PR, not a squash.
- Push with a normal `git push` (the merge resolves the branch up-to-date; no force). Right
  after the push `gh pr checks` briefly reports **no checks reported** for that branch — the
  run has not started; it is not a failed or unpushed state, and polling the same sweep a
  minute later shows the run.

## A doc that mixes hand-written prose with a GENERATED block — restore master's rows, THEN regenerate

Many repos keep one file that is both: hand-written tables of targets/scripts plus a generated
inventory block (an `ARCHITECTURE.md`-style document, a `README` section, a metrics table). On a
conflict, `git checkout --ours <doc>` is WRONG even though the block is derived: it keeps your
side's block and throws away every hand-written row master added while the branch was open. The
damage is silent — the merge resolves, the generator runs, the block-match check passes — and only
the strictest gate reds ("make target `X` is not described in the doc's target tables").

Resolve in this order, and prove with the whole-document gate, never the block gate:

1. `git show origin/master:<doc> > /tmp/doc.master` — master's hand-written text is the base.
2. `git diff $(git merge-base HEAD origin/master)..origin/<branch> -- <doc>` and keep only YOUR
   branch's hand-written lines (rows, paragraphs) from it; the generated-block hunk is not yours.
3. Re-insert those rows into `/tmp/doc.master` at the anchor the branch used (e.g. before the
   `| `pr-body` …` row), write it back, then run the generator target (`make architecture-refresh`,
   `make openspec-index`, the repo's equivalent).
4. Run the strict gate (`make architecture-check` = every target/workflow/script described, not
   only the block) AND the conflict-marker scanner before committing. An auto-merged generated
   block means nothing about the hand-written half.

## A conflict can be MOVED TEXT — follow it into the composer, never assert on its old home

When the branch moves shipped text out of a workflow into a script/target (a composer that the
workflow now redirects into `gh pr create --body-file -`), any test that greps the WORKFLOW for
that text reds after the merge even though nothing regressed. Do not delete the assertion and do
not re-inline the text:

- call the composer instead of grepping the file (`pr_body.refresh_body("<minimal input>")`) and
  keep the ORIGINAL invariant on its output (e.g. "references the tracking issue, never carries a
  closing keyword");
- add the second half explicitly: assert the workflow no longer carries the inline copy and does
  redirect the target (`"<contract sentence>" not in WORKFLOW and "make <target>" in WORKFLOW`).

The pair is the proof that the text moved rather than disappeared, and it is the assertion shape to
copy whenever a "body/title built inline" change lands.

**The same shape when the base moves a RULE out of a recipe into a preloaded skill.** A repo that
slims its agent recipes to "pointer + this run's parameters" deletes the prose your branch just
edited, so the conflict is real but your side is the obsolete home: take the BASE recipe, then move
YOUR sentence into the file that now owns the rule (the leg's `SKILL.md`), and move the test with
it — the assertion grepping the prompt for the wording must become one on the skill file, plus a
prompt assertion that still proves the leg POINTS at that skill (`-s data-search` in the expanded
`make -n`). Deleting the prompt assertion without adding the skill one leaves the wording unpinned;
leaving both reds, because the prompt no longer carries the words by design.

Docs that must follow the same move: the rulebook section, the §8 guard row, and the human-facing
guide (`skills/<name>.md`) each describe the query/rule; a rebase that lands only the code half
leaves the repo with a rule nobody can read. After resolving, grep the resolved tree for the moved
phrase — `git show HEAD:<file> | grep -n '<phrase>'` — on every document that is supposed to carry
it, not just the one the conflict touched.

## A stale bot PR body: recompose it with its target, never hand-edit

A bot PR opened before the body-composer fix carries the OLD body — typically its first
line is the recipe's echoed command (`python3 scripts/<composer>.py render`), which a
heredoc-era step redirected into the body. That shape is a stale artifact, not a defect in
the current code, and hand-editing it just preserves whatever else drifted. Recompose:

```bash
make <kind>-pr-body WINDOW_FILE=/tmp/window.md > /tmp/body.md   # refresh PRs
gh pr edit <N> --body-file /tmp/body.md
```

The composer REFUSES an empty window block (by design — a body without its run window was
the original defect), so lift the existing marker block out of the current body first:
`gh pr view <N> --json body` → take the `<!-- ...-run: <ISO8601Z> run=<id> -->` marker
line, the `started=… · legs: …` line and the run URL into `WINDOW_FILE`. Verify the
result starts with the marker, not a shell command, before editing the PR.

## Slow container gates: run them in the BACKGROUND with a log, never foreground

In a repo whose `make validate`/`make test` shell out to `docker run`, the full gates take
10–15 minutes (a link-resolution stage alone can burn most of it) and print NOTHING until
finished: `make` echoes its recipe line and the python inside block-buffers through the
pipe. A foreground `terminal` call dies on its timeout long before the work ends, and the
killed run tells you nothing. Start them detached and poll the file:

```bash
make validate > /tmp/validate-<branch>.log 2>&1; echo "exit=$?" >> /tmp/validate-<branch>.log
# terminal(background=true, notify=true), then tail the log for `QA PASSED` / `exit=0`
```

Never leave a local suite red or green GUESSED: the whole point of running it before a push
is the exit code at the end of that log. Two of them in parallel is fine (separate worktrees,
separate containers).

**A background run launched BEFORE an edit delivers results that no longer exist.** A long suite is
started, the file it exercises is then edited, and the run finishes minutes later reporting the
failures you already fixed — indistinguishable from a real red unless you correlate it with the code
state it started on (the session id it printed when it detached, or the log's mtime against your
edits). Re-run rather than reporting or "fixing" a pre-edit red; a stale failure report sends you to
re-diagnose code that is already correct.

### While a run is IN PROGRESS its log does not exist — poll the STEP list

`gh run view <id> --log` answers `run <id> is still in progress; logs will be available when it is
complete`, and `--log-failed` fails the same way — a 20-40 minute job spends most of its life
unreadable. Read where it is instead, without a log:

```bash
gh run view <id> --repo <o>/<r> --json status,conclusion,jobs \
  --jq '(.status + "/" + (.conclusion // "")), (.jobs[] | .name + " " + .status + "/" + (.conclusion // ""),
      (.steps[] | select(.conclusion != "success") | "  \(.number):\(.name):\(.status)/\(.conclusion)"))'
```

The step list is the whole diagnosis: the step `in_progress` names what is running, a `failure` names
the gate that stopped the job, and everything after it is `skipped` — which is how you report the REAL
blocker (a step, not "CI failed") instead of guessing from the job name. Fetch `--log`/`--log-failed`
only after `status=completed`, and redirect it to a file before grepping (`> /tmp/run.log`) — the log is
thousands of lines with a `job\tstep\t<timestamp>Z ` prefix per line, so strip that prefix or grep for
the tool's own `[tag]` markers.

### "No checks reported" that never resolves = the PR is CONFLICTING, and GitHub runs nothing
Distinguish the two cases before waiting on a run that will never appear:

```bash
gh pr view <N> --json mergeable,statusCheckRollup   # mergeable=CONFLICTING + rollup [] = nothing scheduled
gh run list --branch <head-branch> --limit 3        # empty: no push run exists for the head
gh repo view --json ... >/dev/null; git log --oneline origin/main -3   # main moved under the branch
```

A head that cannot be merge-tested gets **no workflow runs at all** — not queued, not skipped,
absent. The fix is the rebase + force-push, not a re-push of the same commit and not patience.
That absence is also the cheapest signal that main moved while you worked: re-fetch, rebase every
open branch of yours, and re-run the fast gates, because a conflict resolved in a `.PHONY:`
continuation block or a wiring fixture is the usual casualty.

## A red `auto-merge` with green gates is a CONFLICT, not broken code

When `gh pr checks` shows `validate=SUCCESS live-smoke=SUCCESS guard=SUCCESS` but
`auto-merge=FAILURE`, the PR is `CONFLICTING` — `gh pr merge --match-head-commit` exits 1 on
a conflicting PR, so the merge job reddens even though every gate passed. Diagnose with
`gh pr view <N> --json mergeable,mergeStateStatus` BEFORE touching any test: `CONFLICTING`
means the fix is a merge+resolve+push, not a code change. The red check is the merge job,
not the suite — do not chase tests that were never broken.

### `mergeStateStatus` answers "can it merge", never "is it current"

Do not stop at `--json mergeable,mergeStateStatus`. GitHub reports ONE state, so `BLOCKED` (a required
review) or `UNSTABLE` (a failing check) HIDES that the branch is behind the base — and it is not `DIRTY`
yet only because the base has not touched its files since. Ask divergence directly:

```bash
gh api repos/<owner>/<repo>/compare/<base-sha>...<head-sha> \
  --jq '{status,ahead:.ahead_by,behind:.behind_by}'
```

`{"status":"diverged","ahead":1,"behind":2}` is a real rebase whatever the merge state says, and
`behind_by` is the number the user is asking about. Two consequences worth stating when asked "should it
be rebased": the rebase is the only thing that brings a newly-landed gate/merge workflow under the
branch, and it is the fresh push that makes CI run again — a `workflow_run` merge gate does NOT fire
backwards, so a PR whose green run predates that workflow on the base is never even considered. A
sweeper that reads only `BEHIND`/`DIRTY` will print `pass-over: #N is BLOCKED` and `action=none` for
such a PR forever; that line is not evidence the PR is fine.

### Don't rebase on a guess: `merge-tree` answers "does it actually conflict"

`mergeStateStatus` is `UNKNOWN` for a minute after a push, and `BLOCKED` only means a required check
is still running — neither tells you whether base and branch actually collide. Ask git:

```bash
git fetch origin main
git merge-tree --write-tree --messages origin/main <branch> >/dev/null && echo clean || echo CONFLICTS
```

`clean` = leave the branch alone and let its run finish; rebasing then throws away in-flight checks
and buys nothing. `CONFLICTS` = rebase. Re-check after EVERY merge into the base: a branch that was
clean turns `DIRTY` the moment a sibling touching the same files lands, and each of those rebases is
the same work again — that churn is the queue's cost, not a mistake.

## A stacked child rebases PARENT-FIRST, never onto the base directly

When one PR's branch was cut from another (unmerged) PR's branch — the child needs files the parent
adds — the child is only "behind" relative to its PARENT. Rebasing the child onto the base before the
parent lands DELETES the parent's commits and the branch stops building (its imports/fixtures vanish);
`mergeStateStatus` says nothing about this, and
`git merge-base --is-ancestor origin/main HEAD` is also true for the child, so neither check catches it.

The order is: (1) land the parent; (2) `git fetch origin`, `git rebase origin/main` on the parent;
(3) rebase each child onto the REBASED PARENT (`git rebase feat/<parent>`) — the parent's commits then
become no-ops and the child's PR diff shrinks to its own work by itself; (4) only after a child is
rebased onto a parent that is now on the base, run the child's fast gates and force-push it. A fix
found in a child often belongs to the parent's file: commit it on the parent, then rebase the
descendants — a fix committed only on the top branch leaves every intermediate PR red, and a patch
moved between worktrees with `git diff` will not apply when a descendant added lines in the same file
(`git apply --exclude=<that file>` and edit it in place instead).

**After the parent LANDS, drop its commits instead of replaying them.** Once the parent is squashed
into the base, a plain `git rebase origin/main` on the child replays the parent's own commits and
conflicts file-against-itself — the base carries the squashed equivalent while the child still
carries the originals. Replay only what the child added:

```bash
git log --oneline origin/main..HEAD        # the last commit belonging to the PARENT's issue is the marker
git rebase --onto origin/main <parent-tip-commit>
```

Commits that only re-apply content the base already has become no-ops, and the child's diff shrinks
to its own work by itself.

**CI does not respect a stack's order: the TOP child can merge first and supersede its parents.**
Every branch in a stack builds and goes green alone, so the superset branch is a valid merge target
and `auto-merge` will land it — that squash puts every parent's content on the base, and the parents
are now obsolete while still OPEN. They read `CONFLICTING`/`DIRTY` and their remaining diff is
strictly BACKWARDS:

```bash
git diff --stat origin/main <parent-branch>   # only deletions, and only of files the SIBLING added
```

Read that shape as "already landed", never as "needs resolving". Do NOT rebase a parent down to an
empty PR and do NOT merge it — merging would DELETE what the child added. Close it with the evidence:
the base sha, the gates you ran on a clean worktree of that sha (`make check-…`, all exit 0), and one
line saying the work shipped in the other PR. Then close the ISSUES the parents would have closed:
their `closes #n` never fired, because the PR that would have closed them is the one you just closed.
Comment on each with the merge sha and what was verified on it; never close one silently.

## When YOU own the `auto-merge` gate: cross-repo heads, and a "green" that means every job SUCCEEDED

Writing or repairing the merge job itself is a different task from landing a PR through it, and four
mistakes there are silent:

- **A same-repo head condition skips every fork-opened PR.** `head.repo.full_name == github.repository`
  is correct only where the bots push branches INSIDE the repo; where agents push to a personal fork and
  open cross-repository PRs it disables the gate for every PR the repo opens. Allow the base repo **or** the
  fork owner (`head.repo.owner.login`), one owner, never a wildcard or a negation — and keep third-party
  forks manual.
- **`--delete-branch` is a base-repo action.** For a fork head it fails AFTER the merge succeeded, turning
  a green merge into a red run. Read `headRepository` from the same `gh pr view` and omit the flag; print
  that the branch stays.
- **`!failure()` is not "green".** A SKIPPED job satisfies it (a collapsed matrix, a job cancelled by a
  concurrency group), so merge on `needs.<job>.result == 'success'` for every PR-relevant job — and keep a
  push-only job OUT of `needs:`, since a skipped need skips the dependent job unless the `if:` tolerates it.
- **A new job/step does nothing for PRs already open.** A `pull_request` run starts on a push (or a manual
  re-run), and a re-run replays the SAME merge ref, which predates the new job. An already-open PR needs a
  push/rebase before the gate can see it; a stale `mergeStateStatus: BLOCKED` on it clears with that run.
- **A fork head's `pull_request` run carries NO repository secrets.** GitHub withholds secrets from a
  fork-triggered run, so an auto-merge job there reads an EMPTY token and defers on every fork PR while its
  checks stay green (a deferral is exit 0 — nothing reddens). Move the merge into a
  `workflow_run: [completed]` workflow in the BASE repo: the run belongs to the base repo, so the token is
  present. Check out the base branch, never the PR head (the job holds a write token), and make a missing
  token an explicit `exit 2` with an `::error::`. Bootstrap caveat: that trigger only fires once the workflow
  exists on the default branch, so the PR introducing it needs a human merge — never tell the user the queue
  is now self-merging before it is.
- **A `REVIEW_REQUIRED` ruleset cannot be satisfied by the PR's own author — so the merge bypasses that
  one block.** GitHub refuses `gh pr review --approve` on your own PR (`Review Can not approve your own pull
  request`), and in these repos one identity (the owner PAT) opens every PR, so an approval step can NEVER
  succeed for the normal case. That makes the approval path dead code: do not keep both. The merge job
  squash-merges such a PR with `gh pr merge --admin --squash --match-head-commit <sha>` — but ONLY as the
  last branch of the decision, after the author gate has accepted the opener (repo owner, a collaborator
  with WRITE permission, or the bot, authorised by the CI run's actor). Everything else still defers: a
  stranger's green PR, a conflict, a stale branch, a draft, and `do-not-merge`. The bypass lives INSIDE the
  workflow script as one explicit branch with a printed reason — never a blanket `--admin`, and never a hand
  `gh pr merge` from your shell (the agent does not merge; the job does). Diagnose in one pass before
  designing anything: `gh api user --jq .login`, `gh api repos/<o>/<r>/collaborators/<login>/permission`,
  then per PR `--json headRepositoryOwner,reviewDecision,mergeStateStatus,mergeable`.
- **`--admin` failing is a token-permission finding, not a signal to defer quietly.** The job's PAT needs
  admin (or a ruleset bypass) on the base repo; a write-only token fails the bypass. Print the reason and
  let the run go red — a bypass that silently degrades to "deferred, exit 0" reproduces the invisible
  green-and-never-merges state this whole section exists to kill.

After the merge, prove the closing references actually bound: `gh pr view <n> --json
closingIssuesReferences` then each issue's `state` — an unparsed `closes #n` leaves the issue open under a
green run. Repo-specific depth (the author gate, the `--admin` branch, the run→PR lookup, the rebase sweep's
comment hold): `references/fork-pr-automerge-and-rebase.md`.

## A `workflow_run` merge job must RESOLVE its PR without the runs endpoint

A merge job triggered on `workflow_run` gets no PR number in its payload (the event is a run,
not a pull request), so it resolves one from the run. The obvious call,
`gh api repos/<o>/<r>/actions/runs/<id>/pull_requests`, returns **404 for a run started by a
fork PR** — and under `set -euo pipefail` that 404 kills the step before any fallback line,
so the job dies on the lookup and never reaches the merge decision. Symptom: CI run green,
merge run red, PR still open.

- Do not lead with that endpoint under `set -e`. Guard it (`… || true`) or skip it and
  search by branch.
- The fallback must be `gh pr list --search "head:$BRANCH" --state open --json
  number,headRepositoryOwner`, then keep the row whose `headRepositoryOwner.login` matches
  the run's head owner. `--head <owner>:<branch>` matches a SAME-REPO branch only and
  returns nothing for a fork head — measured.
- Verify the resolved PR's head repo is the fork before merging; a same-name base-repo
  branch reaches the same code path.

Depth and the exact failing log shape: `references/fork-pr-automerge-and-rebase.md`.

## The rebase sweep: a status comment is not a claim

`scripts/rebase_bot_sweep.py` skips a PR when it thinks another bot holds it. If the claim
reader treats ANY comment as a claim, an ordinary status comment parks the PR and the sweep
prints `pass-over: #N ... no open PR needs rebasing` while the branch IS behind base.

- Hold only on the bot's explicit claim marker; arbitrary comments never hold a PR.
- `NEEDS` = `BEHIND` and `DIRTY`. `BLOCKED` is a review state and not a rebase trigger on its
  own — but a PR that is `BLOCKED` **and** behind base still gets rebased.
- When a test fixture "posts a claim", use a marker the regex actually matches; a fixture
  with a non-matching word silently exercises the no-claim path and locks nothing.
- **A fixture that answers a read the code never compares locks nothing either.** The two
  shapes: an EMPTY answer (`branches.json = []` for a ref list the code then compares against a
  prefix) means the comparison branch is never executed; a WRONG SHAPE (a list of strings where
  the API returns `[{"ref": …}]` objects, so the parse yields nothing) is worse, because it looks
  like coverage. When you fix a "this guard never fired" defect, make the fixture answer in the
  REAL shape and require the new case to fail on the pre-change file (`git stash push
  scripts/<file>` → RED, `git stash pop` → GREEN) — that pair is the only proof the pin bites.
- Verify a branch is actually behind before arguing about it:
  `gh api repos/<o>/<r>/compare/<base>...<branch> --jq .status` (`diverged`/`behind`).

## A red `openspec-index-check` is a SYMPTOM — prove the PR implements anything at all

Before you "just regenerate the index", read WHAT the failing PR put on disk. An
agent-implemented PR can ship the change's *scaffolding* and none of its work: a
`proposal.md` + capability spec describing an edit to a rule/prose file, with

- **no actual edit to the file the proposal names** (`git diff --stat origin/master...<branch>`
  shows only `openspec/changes/**` + a test module — the rule sentence is untouched);
- **no `tasks.md`** in the change directory (the tasks gate only inspects changes that
  have one, so nothing complains);
- **two change directories for the SAME edit**, one filed from a since-CLOSED issue;
- **test-reference lines naming a file that does not exist** (`- **Test:**
  tests/test_<module>.py::<test>` while the real pin lives in a different module and that
  file was never created). `openspec validate` checks structure, not whether the reference
  resolves, so a scenario can cite a test that does not exist and the gate stays green.

So the index failure is the LAST symptom of a hollow change, not its cause. Regenerating
and pushing would land a green PR that implements nothing. Verify in this order:
`git diff --stat origin/master...<branch>` (is the named file really edited?) → every
change dir has `tasks.md` with ticked boxes → one change per edit (drop the duplicate and
its spec) → each `- **Test:**` path exists and the named symbol is in it
(`grep -n "def <test>" <path>`). Then regenerate, and PROVE the pin is real: run the test
against the pre-change version of the file (`git checkout <file>` swap or
`git stash` of that one path) and watch it FAIL, then re-apply and watch it pass. A pin
that is green both ways locks nothing.

## A green-tree PR red on `openspec` alone is bookkeeping, not code

In a repo whose `ci-unit`/`openspec` job runs `openspec-tasks-check`, a fresh change ships
`- [ ]` boxes and the job reds with every test green. Tick each task as it is verified, and check
before pushing:

```bash
python3 scripts/check_openspec_tasks.py    # bare: per-active-change OK/FAIL, exit 1 on any unticked box
```

Passing an argument makes it resolve a change **named** that argument, so `… check` prints the
misleading `FAIL check: no active tasks.md (archived/missing)` — run it bare.

**An agent PR body can CLAIM "every box ticked" while the file has none.** Read the change's
`tasks.md` off the PR head instead of trusting the body. Tick a box only after proving the work it
names exists, and prove it the cheap way — run the new guard module against the PRE-change base
(a worktree at the base sha with only the branch's test file copied in) and require it to FAIL:
`AttributeError: module … has no attribute <new symbol>` / `KeyError: '<new key>'` is that proof, and
it doubles as the "test that fails on the old code" evidence the tasks file usually demands. A box
about docs is the one that is genuinely still open in most agent PRs (the rulebook section, the
§8 guard row, the skill paragraph): write those before ticking, not after. The generated index is a
SECOND, independent failure behind the task gate — the task gate stops the run first, so a green
index check you ran earlier says nothing about the tasks file.

Three specifics that cost a round each, full recipe in
`references/openspec-bookkeeping-repair.md`: the index row's Issue column is parsed from the
proposal's `Issue:` header, so an agent's prose there becomes an unreadable cell (write
`Issue: #<n>`); `findings.md` fields must be LIST ITEMS (`- **Evidence:** …`), because a bare
`**Evidence:**` line is invisible to the parser; and the task gate inspects EVERY active change,
so the full suite fails on your own unticked verification box — verify, tick it WITH the evidence
(`make validate → QA PASSED`, `PASSED N | FAILED 0`), regenerate, and only then run the suite.

## `pull_request` checks out the MERGE COMMIT — that is why a generated index keeps re-staling

A `pull_request` job checks out the merge result by default, so a GENERATED index that every
change edits (OpenSpec) is verified against a tree carrying every OTHER open change. A
branch whose index was current when written reads stale the moment a sibling merges — the
same branch goes red on every merge, and regenerating around it is the symptom loop. The
root-cause fix is at the pipeline, not the branch: check out the PR's own head
(`github.event.pull_request.head.sha`, falling back to `github.sha` on a push) so the gate
verifies the tree that produced it. Master's own index is still verified by that pipeline's
push run, and `auto-merge` still matches the validated head SHA, so what merges is what was
checked. Guard the `ref` expression and that `fetch-depth: 0` survives.

## Verify a merge for markers BEFORE `git add -A` + commit + push

A `git merge` that conflicts leaves `<<<<<<<`/`>>>>>>>` markers in the file; `git add -A`
stages them happily and a push ships them to the remote, where they redden the PR and you
must repair them after the fact. After ANY merge into a branch, grep for the markers AND
parse-check the file (`python3 -c "import ast;ast.parse(open(f).read())"`) BEFORE
committing — a marker is invisible to git (the file is "resolved") and only a syntax run
catches it. If you already committed and pushed, union-resolve the markers
(`re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S).subn(lambda m: m.group(1)+m.group(2), s)`),
re-verify the file parses and has zero markers, then re-commit and re-push.

## Protected repo rule files (`AGENTS.md`, contracts) — the write decides resolvable vs HARD STOP

Whether `AGENTS.md`/`README.md` rule-section conflicts are resolvable depends on whether the
WRITE actually proceeds, NOT on the repo having the file:
- **If the edit is REFUSED by an approval gate** (some repos block the agent's write to a
  protected rule file): HARD STOP. Abort the rebase, leave the worktree clean, and hand the
  user the exact resolution (take the branch's paragraph + new guard row on top of master's
  text) rather than half-finishing it. Never work around the refusal — not through `terminal`,
  not through `execute_code`: an approval prompt that TIMED OUT is a refusal (silence is not
  consent). If the change tracks the row as a task, mark that box
  `- [~] … — blocked: <who/why>` (the tasks gate accepts it and reports review-required; a bare
  `- [~]` fails), quote the exact row in the PR body so a human can paste it, and land the rest
  of the change.
- **If the write goes through** (git allows it, no approval gate trips — e.g. llgenie): it is
  a normal conflict, not a stop. When main has SQUASH-MERGED a sibling PR that added a rule
  section into the same docs the branch also appends to, the two edits are pure ADDITIONS →
  resolve as a UNION that KEEPS BOTH sides' added sections (master's section AND the branch's
  section), never either/or. A naive take-HEAD or take-ours silently deletes one PR's rule.
  After the union, grep-count each side's section anchor on the resolved file (== 1 for
  both), exactly like the Makefile union, because the later-commit re-drop trap applies to
  prose sections too.
- **A markdown README union must join the two kept sections with a BLANK LINE.** The repo's
  `make lint` gate enforces `markdown headings not preceded by a blank line`, so gluing a
  branch's `##` section flush against master's `##` section reddens CI (`linux / lint`) even
  though the conflict itself resolved cleanly — the marker is gone and the gate still trips.
  When you CONCAT two README sections during a union, join them with `\n\n`, never a single
  newline, and run `make lint` locally before pushing. Same gate class as the list-continuation
  backslash: resolved-on-the-surface, still red.

  Regression-test the gate, not the text: after a clean repro of the concat with a blank line,
  confirm `make lint` prints `LINT OK` (it checks both the trailing newline and the
  blank-line-before-heading rule), then check the whole batch — a red lint on a rebased PR is
  almost always this join, not the conflict resolution.

## Confirm WHICH remote the PR's head lives on before you push (a fork PR heads the FORK)

A PR opened from a fork has its head branch on the FORK, not on the base repo. Pushing the
rebased branch to the wrong remote silently CREATES A STRAY BRANCH on the base repo instead
of updating the PR — and the PR still reads `CONFLICTING`, so the mistake is invisible
unless you read the push output (`* [new branch]`) and re-read the PR's `headRefOid`.

- **For a branch that has no PR yet there is nothing to read — run `git remote -v` BEFORE the first
  push.** Typically `origin` is the UPSTREAM and the personal fork is a second remote (`fork`), so
  `git push -u origin feat/<name>` opens a stray branch on the base repo. Recover with
  `git push origin --delete feat/<name>`, push to the fork, and set the upstream to it; then open the
  PR with `--head <fork-owner>:<branch>`. Read the push output (`* [new branch]`) and the remote URL
  in it — that line is the only place the mistake is visible.
- **An EXISTING PR does not make a bare push safe.** A fresh worktree's branch carries no upstream even
  when the PR is already open, so `git push origin <branch>` still creates a stray branch on the base
  repo (`origin`), prints `* [new branch]`, and leaves the PR's `headRefOid` untouched — measured on a
  branch whose PR existed, where the mistake was visible only in that one push-output line. Read
  `gh pr view <N> --json headRepositoryOwner` and push `<fork-remote> HEAD:<branch>` by NAME every time
  (delete the stray with `git push <base-remote> --delete <branch>`); never rely on the branch having a
  tracking remote just because the PR is green.
- Read the head FIRST when a PR DOES exist: `gh pr view <N> --json headRefName,headRefOid,headRepositoryOwner`.
  `headRepositoryOwner.login` tells you which remote owns it; in some clones `origin` is the
  UPSTREAM and the personal fork is a second remote (`git remote -v` — do not assume
  `origin` is yours).
- Push to that remote explicitly: `git push --force-with-lease <fork-remote> HEAD:<branch>`.
- Verify by OID, not by "push succeeded": `git ls-remote <fork-remote> <branch>` and the PR's
  `headRefOid` must both show your new commit. `mergeable` flipping `CONFLICTING` ->
  `MERGEABLE` is the independent confirmation the PR actually got the rebase.
- If you did push to the wrong remote, delete the stray: `git push <base-remote> --delete
  <branch>` (it is a branch you created; removing it restores the repo), then push to the
  correct one.

## A rebase re-authors the commit — it can trip a PR-author guard that was green before

A repo's PR-author guard compares the FULL identity string (name + email), and the
name must match EXACTLY. A rebase or `--amend` re-creates the commit with the LOCAL
git identity, so a branch that passed the guard before can fail it after a rebase —
the guard only surfaces once it merges into the base, which may be after you opened
the PR. Before pushing a rebased PR:

- Read the allowlist's exact expected name: `grep -nE 'ALLOWED|user.name' scripts/check_pr_authors.py`
  (or the repo's equivalent). It is usually `Andy Holst <…>` / `Asimov Agent <…>`, and
  `andyholst` (lowercase, no space) is a DIFFERENT identity that fails.
- Confirm the local identity matches: `git config user.name; git config user.email`.
- If it does not, set it and re-author the single commit, keeping the message:
  `git config user.name "Andy Holst" && git config user.email <email> && git commit --amend --reset-author --no-edit`.
- Re-run the guard locally (`make check-pr-authors`) and confirm `OK` before pushing.
- **The subject has its own gate.** A typed Conventional Commit subject is matched literally, so
  `docs( readme ): …` (spaces inside the parens) or a stray leading space fails a
  `check-pr-hygiene`-style gate that reads the subject; write `type(scope): imperative summary`
  and re-read `git log -1 --format=%s` after any `--amend` before pushing.

A CI failure that names a commit author is this guard, not a test regression — do not
chase the tests.

## CI red but `make test-unit` green locally — read the job log, it is a guard, not a test

When a CI job fails but the same suite passes locally, the failure is in something the
CI job runs BEYOND the unit suite (author guards, docs, wiring, dispatch-forms) — not a
test regression. Read the actual job log (`gh run view <id> --log-failed`) before
touching any test. The usual cause is a NEW guard that merged into the base after you
opened the PR, so it runs against your branch for the first time on this push. Fix the
guard violation (author identity, docs line, wiring), re-run that gate locally, and
re-push — do not "fix" tests that were never broken.

Four things to read before you touch the branch:

- **The failing STEP, not the job name.** A `unit` job runs the gate chain BEFORE pytest, so the run can
die in a `check-*` / generated-artifact gate with the tests never executed (`make[1]: *** [Makefile:<n>:
check-<artifact>] Error 1` after the pytest summary would have printed). `gh run view <id> --json jobs --jq
'.jobs[] | .name, (.steps[] | select(.conclusion=="failure") | .name)'` names it in one call; a job that
reports 0 tests run is a gate, not a suite.
- **Whether that gate is red on the BASE branch too.** Run it in a detached base worktree
(`git worktree add --detach ../wt-base origin/main && make <gate>`) or read `gh run list --branch main`.
A gate already red on the base is not your regression and it blocks EVERY PR, so the PR's job changes
from "fix my tests" to "fix the gate's root cause" — do that in the same PR (it is the only way to green
it), file the defect as its own issue, link issue and PR both ways, and say so in the PR body ("the gate
that was red on `main` itself, which is why the job died before pytest").
- **The SAME environment CI uses.** A gate that passes on the host can fail in the test container (a
  different cache, a different token, a different working tree). Re-run the exact command inside the
  repo's test image (`docker run … <test image> python scripts/<gate>.py …`, or the `make` target) before
  believing the host result.
- **A gate that re-derives from a live external service** is the usual shape of "red on base, every PR":
  compare content and report the re-reads instead of byte-comparing. See `derived-document-generators` →
  the live-source gate pitfall.

**Fetching a job log that `gh run view` refuses:** `--log`/`--log-failed` answer either `still in progress`
or `the response contains terminal escape sequences`. For a completed job go around it:

```bash
gh api --allow-escape-sequences /repos/<o>/<r>/actions/jobs/<job-id>/logs \
  | sed 's/\x1b\[[0-9;]*m//g' > /tmp/job.log
```

**Batch the pushes.** Every push cancels the in-flight validation and starts a full pipeline again, so
sweep the branch for the remaining doc/test/gate edits and land them in ONE push; a doc-only commit pushed
to unblock a 15-minute run throws that run away and buys nothing. Only push again once the new failure is
actually fixed.

## Sweep the queue, don't guess the merge order

End each pass with a single status sweep: `gh pr list --state open` + `gh pr checks <n>` per
PR + `gh run list --branch master`. Track every open PR and the master head; report which
PRs are rebased-and-in-CI versus which a merge just re-conflicted. New PRs appear while you
work — always re-list the queue before declaring it done. A refresh/bot PR can appear mid-pass:
it is bot-owned, so check its `fix-bot` run (and the `fix-bot-start` window comment) before
touching it — a live repair holds the branch and push-only-when-green means your commit would
race it.

- **A resume starts from the FORK head, and a rebase bot may already have moved it.** `gh pr view
  --json commits` can answer a stale list; the authoritative head is
  `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`. When a local branch trails it, `git reset --hard
  <remote>/<branch>` — where `<remote>` is the CONFIGURED remote name (`git remote -v`; often `fork`),
  never the owner login (`git fetch andyholst …` → `does not appear to be a git repository`), then
  confirm the reset base is current: `git merge-base --is-ancestor origin/main HEAD`.

- **A bot can also push onto YOUR branch between your push and your verification.** A sweep that
picks an issue whose PR is already open resumes that branch and commits `feat(...): implement <n>`
on top of your work, then dies at `gh pr create` ("already exists") — so the PR head moves while you
think you are done. Before reporting, re-read it: `git fetch origin`, compare
`git ls-remote origin <branch>` with the SHA you pushed, and if it moved, `git reset --hard
origin/<branch>` in your worktree and re-run the fast gates on the NEW head. Do not revert or
force-push the bot's commit: it is peer work, the PR is still squash-merged, and if it broke
something you fix forward. A duplicate implementation landing on your branch is the symptom of a
broken queue hold, not of your branch — diagnosis (`make issue-queue` rows, the pick job's log
line naming the issue it took) belongs in its own filed issue, not in your PR.

**Keep your worktree until the deliverable is verified.** Deleting it right after the push leaves
the session with no tree to reproduce a failure in, no artifact behind your claims, and no place
to make the follow-up edit — and any "prove the gate bites" re-run needs the branch checked out.
Remove it only after the PR is MERGED/verified (`sudo rm -rf` + `git worktree prune` when docker
left root-owned `__pycache__` files; wipe inside a container instead of fighting the ownership).

If `gh` answers `none of the git remotes configured for this repository point to a known GitHub
host`, pass the repo explicitly (`gh pr view <n> -R <owner>/<repo> …`) instead of debugging the
remotes — and then check `git remote -v` anyway: a wrong `origin` is the usual cause and it must
be repaired (`git remote set-url origin <url>`) before any fetch or push.

## Before rebasing an OPEN PR that is not yours: check it is not another agent's live work

`make worktree-resume BRANCH=<b>` REFUSES when the local branch carries commits that are not
on origin ("resetting it would discard them") — that refusal is a SIGNAL, not an obstacle.
Verify it before working around it:

- `git worktree list | grep <branch>` — an entry means another agent owns a worktree for it;
- `git rev-list --left-right --count <branch>...origin/<branch>` — local ahead means unpushed work;
- compare the local commit's timestamp with `date -u`: minutes-old (or seconds-old) is an
  agent working NOW, not a stale leftover.

A live worktree + local-ahead commits = ANOTHER agent's in-flight PR. Do NOT rebase it, do
NOT force-push it, and do NOT reuse its worktree (one agent, one worktree). Leave it, report
it as owned by another run, and spend the pass on the PRs nobody holds. A stale branch with
no worktree and old commits is safe to resume.
