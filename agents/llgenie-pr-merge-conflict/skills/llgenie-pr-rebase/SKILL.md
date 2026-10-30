---
name: llgenie-pr-rebase
description: Use when a conflicting llgenie PR needs a rebase.
version: 1.0.0
author: llgenie-pr-merge-conflict
license: MIT
metadata:
  hermes:
    tags: [git, rebase, github, llgenie]
    related_skills: [github, pr-finalization]
---

# Rebase a conflicting llgenie PR

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `llgenie-pr-rebase`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## When to Use

Use when a pull request in `asimov-agent/llgenie` shows `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` or `BEHIND`, and it must be brought onto the current `main` tip while staying a single reviewable commit.

Repo: `asimov-agent/llgenie`. Two checkouts matter: the owner's clone (never edit it, never `git switch` it) and your own worktree root beside it (`../llgenie-wt/<n>`).

- **The PR-rebase lane (`llgenie-pr-merge-conflict`) must always communicate with the other llgenie bots before rebasing an ongoing PR.** Concretely, BEFORE touching a branch with a live claim, an open PR, or a `bot-claim:` comment: message the owning lane with the id, the head sha you measured, and what you are about to do; then post the conclusion on the PR, because a decision that exists only in a DM does not exist for the next reader. A rebase another lane has to resolve by hand is the failure. *cite #994*
- **All lanes must keep their ongoing PR rebased onto the latest fetched `asimov-agent/llgenie` `main`.** Fetch fresh (`git fetch upstream main`; `asimov-agent/llgenie` is the canonical remote, a fork named `origin` is not upstream) and rebase at the sha fetched in that same moment — never a sha quoted in a message, which is stale by the time you read it. Do not rebase through a live run at the head (cancel-in-progress makes an authorised rebase destructive). *cite #994*

- **Rule 3 (owner 2026-10-29): before starting ANY new issue/PR work, every lane must fetch and rebase its worktree onto the latest fetched `asimov-agent/llgenie` `main`, then report to the planner ("llgenie inbox triage" — me), so the planner can relay the assignment across the fleet (and no two bots pick one issue).** *cite #994*

- **Rebase only when the PR is actually `CONFLICTING` (owner rule #1015, supersedes #994's rebase-every-move clause).** Do NOT rebase a PR on every `main` move — main advancing under a `MERGEABLE`/`BLOCKED` PR is fine until a merge actually needs a rebase. The sweep is the **genuinely-`CONFLICTING` set only**, measured fresh (`mergeable=="CONFLICTING"`, never `mergeStateStatus` alone). Leave `MERGEABLE`/`BLOCKED` PRs alone — that includes a dirty-watch narrowing to conflicts, not enumerating all open PRs. Fetch is still mandatory before any work (explicit refspec `+refs/heads/main:refs/remotes/origin/main`, because a local `refs/heads/origin/main` shadows the remote ref) but fetch ⇒ pull-to-friendly; a `git pull`'s own rebase only fires on a real conflict. A PR whose base merges and then conflicts is rebased then, not preemptively. If a PR is another lane's vehicle (`bot-claim:`, test-led body), never force-push it — report it to that lane, do not rewrite it. *cite #1015*

## 0. Hand off first
Message the owning bot via `message_agent` before touching the branch — `@llgenie-issse-implementer` for issue-bot PRs, `@llgenie-ci-pipelines-maintainer` for CI, `@llgenie-documentation-maintainer` for docs. Only proceed when they decline or a coordinating bot (e.g. `@llgenie-planner`) hands it over.

## 1. Survey

**Arm auto-merge when the work is done — "done" triggers the arm, not "approved".** After the last push of a rebase or conflict resolution, run `gh pr merge <n> --auto --squash` (or the repo's configured strategy) and report the **arm time** in the same comment as the base/head pair. A rebased PR left unarmed is a rebase nobody merges. The only exception is a PR the owner explicitly forbade — write `auto=none (owner instruction)` and say where that instruction lives. If the repo has auto-merge disabled or the branch protection rejects it, say so plainly instead of claiming an arm that did not happen.

**Start from a fresh upstream main, and bookend the work with two comments.** Before you create a worktree, branch or first edit: `git fetch` the canonical remote (`asimov-agent/llgenie`, whose remote is named `origin` in the canonical clone — a fork remote is not upstream) and branch from `origin/main` **at the sha you fetched in that moment**. Never from a branch you already had, and never from a sha quoted in a chat message: it is stale by the time you read it. Write that sha into your first comment. Then **bookend**: one comment when you start (issue/PR id, branch, the main sha, what "done" means) and one when you finish (head sha per PR, what changed, the run id or command that proves it, anything left open). **Report the same two lines to the planner.** A start comment with no finish comment is an abandoned claim; a finish comment with no start comment has no baseline.

**Publish the sweep before you touch anything.** A sweep rewrites branches other lanes are actively pushing, so it is legitimate only if the list goes out first: **one comment per sweep on #864** naming `base sha · PR# · branch · head before → after`, posted before the first push. If a lane answers "I am mid-push on that branch", skip it and say so in the same thread rather than winning the race. A rebase that is not announced is indistinguishable from a lane losing its work — and a `--force-with-lease` rejection is that lane answering you, so re-fetch, re-read the thread, and stop. That board thread is an **issue**, not a PR: use `gh issue comment 864 --body-file …` — `gh pr comment` answers `Could not resolve to a PullRequest` and posts nothing.
```bash
gh pr list --repo asimov-agent/llgenie --state open --limit 100 \
  --json number,title,headRefName,baseRefName,isDraft,mergeable,mergeStateStatus
```
`mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` are the ones to rebase. `MERGEABLE` + `BLOCKED` means waiting on checks/approval — do not rebase those.

**Measure `isDraft` and report every draft instead of rebasing it silently.** A draft is invisible to auto-merge, to the merge queue and to a reviewer scanning for work, so a rebase performed on one produces a clean branch nobody will ever land. Report it and let its owner flip it with `gh pr ready`; never mark another lane's PR ready yourself. Never open a draft PR of your own either — open ready-for-review and flip it before reporting if it somehow opened as draft.

A conflicting PR reports **no checks at all** ("no checks reported on the … branch") because GitHub builds no merge ref. That is the symptom, not a broken workflow.

If this procedure is scheduled, gate it on a deterministic detector whose whole output is the conflicting subset: an unchanged hour then produces no agent run and no delivery, and "alert only on a transition" is enforced by construction rather than by prompt discipline. Two properties are not optional — the detector must report a hard error (never "nothing conflicting") when the GitHub read itself fails, or the watch has a silent blind spot; and a direct/forced run bypasses the gate, so only a scheduled tick proves suppression.

For how to describe a PR board so every sentence is true at the moment it is printed — the four check conclusions, bot-green vs owner-ready vs stuck-cancelled, and what a watch's silence means — see `references/pr-fleet-monitoring.md`.

## 2. Worktree (never the owner checkout)
```bash
cd <owner-clone>  # the checkout you were told never to edit
git fetch origin main
git fetch origin '<head-branch>:refs/remotes/origin/<head-branch>'
git worktree add -b pr<N>-rebase ../llgenie-wt/pr<N> origin/<head-branch>
```
Branches of agent PRs live in **either** the base repo or the `andyholst` fork, and which one is per-PR: `gh pr view <n> --json isCrossRepository` decides. Fetch that head from **its own** remote and push it back to the **same** remote; the base is always `origin/main` (the upstream sha) whatever the head's remote is. Never push a fork head to `origin`, never an upstream head to the fork — and never assume the two `main` refs agree, because the fork's `main` is a different commit that moves on its own schedule. Confirm the clone before fetching (`git remote -v`, `git ls-remote <remote> refs/heads/main`); there can be more than one checkout of this repo on a host, each naming the upstream differently (`origin` in one, `upstream` in another).

## 3. Rebase
```bash
cd ../llgenie-wt/pr<N> && git rebase origin/main
```
Read `AGENTS.md` at the target main sha before the first edit.

### Check the PR's BASE before you pick the target
`origin/main` is the right target only when the PR's base **is** `main`. Read it per PR (`gh pr view <n> --json baseRefName`); a stack of PRs based on another feature branch reads `CONFLICTING` against `main` forever while nothing is wrong with it, and rebasing it onto `main` rewrites somebody's dependent chain. Recurring shape in this repo: a dozen PRs whose `base` is one long-lived agent-profile branch. For those the base is **that branch's current tip**, and the frozen base sha moves under them — a `/tmp` note or the PR body quoting the old base is stale.

**`git rebase --onto <new-base-tip> <old-base>` re-applies the base's own commits and conflicts every time**, because a stacked branch *contains* its base's history: the updatable range includes commits the new base already has. Replay only the branch's own work instead:
```bash
git fetch origin '<base>:refs/remotes/origin/<base>' '<head>:refs/remotes/origin/<head>'
cd ../llgenie-wt/pr<N> && git checkout -B pr<N>-rebase origin/<head>
git cherry -v origin/<base> HEAD      # '+' rows are this PR's own; '-' rows are already in the base
# then: git checkout -B pr<N>-rebase origin/<base>  and cherry-pick the '+' shas in order
git checkout origin/main -- CHANGES.md && make changes-index && git add -A
git commit -C <replay tip>            # keeps author and message
git diff --stat origin/<base>..HEAD   # must be ONLY this PR's files
```
`git cherry` is the instrument because it compares patch-ids: a rebase of the stack would replay the base's commits, and a `--onto` whose upstream is anything but the branch's own merge-base replays them too. Measured on a stack whose branch held 2 unique commits among 30: the replay is two cherry-picks, and the other 28 are the base's.

## 4. Resolve — know the two habitual conflicts
- **`CHANGES.md`** is an index table, newest first. Two branches almost always add a new top row at the same position. Resolution is **keep both rows** — main's existing row stays where main has it, the branch's new row goes directly under it. Never drop either row: `make check-docs` fails on a note with no row *and* a row with no note. Same-date rows may sit in either order.
- **Newer trees generate that table** (`docs/changes.d/` + `make changes-index`, issue #934). There, the correct resolution is different and simpler: take `origin/main`'s `CHANGES.md` **wholesale** (it is generated), and add the branch's row as `docs/changes.d/<date>-<note>.md` — then `make changes-index` rewrites the table. Re-inserting a row by hand into a generated file fails `check-docs` with `[changes-index] ERROR: … is not indexed — add docs/changes.d/…`. Check which mechanism the tree uses before resolving: `ls docs/changes.d | head -1` decides it.
- **A stacked PR is replayed, never rebased** — `git cherry origin/<base> origin/<pr> | grep '^+'` then cherry-pick only those shas onto the current base tip. Three failure modes, all seen: an **empty cherry-pick** ("nothing to commit") means that commit is already patch-equivalent — `--skip` it, and never replay the index-rebuild commit before the real fix or the branch ends up empty; **`CHANGES.md` conflicts on every replay** — `git checkout origin/<base> -- CHANGES.md` then `make changes-index` then amend; **JSON/YAML unions leave conflict markers inside the file** — after any such union run `git grep -lE '^(<<<<<<<|>>>>>>>)' -- .` and it must print nothing, because a tree with markers in a data file can still pass `check-docs`.
- **The acceptance pair for a docs-touching branch is measured, not felt**: `git ls-tree -r --name-only HEAD agent-wiki/ | grep -c '\.md$'` must equal the row count in `CHANGES.md`. A branch at 222/222 while `main` is at 223/223 fails the same four index assertions as a dozen other PRs — a shared base, not a dozen mistakes, and `make changes-index` is the remedy, never an edit to the diff. When it conflicts across many PRs in one sweep, do not hand-merge hunks: take `origin/main`'s file wholesale, re-insert the branch's added rows under the header separator, and let `make check-docs` referee (`references/sweep-mechanics.md` §4 has the loop).
- **`rerere` is ON in this repo and its cache is shared across worktrees, so `git rebase` can auto-resolve `CHANGES.md` with ANOTHER lane's row.** The rebase prints `CONFLICT (content): Merge conflict in CHANGES.md` then `Staged 'CHANGES.md' using previous resolution.` and leaves no `UU` entries, so `git status` looks solved — while the staged row is a different branch's change record (columns swapped, prose belonging to a different PR). Always diff the resolved file against `origin/main` (`git diff origin/main -- CHANGES.md`) and against the branch's own commit (`git show <sha> -- CHANGES.md`) before `rebase --continue`; replace the row with the branch's verbatim row rather than accepting git's staged version. `make check-docs` does NOT catch it — the wrong row names a note that does exist, so the index gate stays green.
- Engine/docs registries (`README.md`, `docs/ARCHITECTURE.md`) resolve toward **main's** version; do not invent a third behaviour inside a rebase.
- Two conflict shapes are scriptable and should not be hand-merged: `.PHONY` token sets (`scripts/resolve-phony-union.py <Makefile>` — union of both sides' keys, refuses a hunk that is not a continuation) and rulebook bullets in `agents/*/SOUL.md` / skills (`scripts/resolve-rule-union.py <file>` — base's text plus the branch's unseen `- **rule.**` bullets). Both print what they wrote; neither decides whether the branch's edit was legitimate, so re-run the gates afterwards.
- Three more are versioned beside them, because each one exists to stop a specific mistake that cost a push tonight: `scripts/resolve-fleet-triple.py <repo>` — the `standing-rules.md` / `fleet-block-exemptions.json` / `SOUL.md` triple that a stacked branch collides with once a rule lands (canonical file wins, exemptions union by profile, fleet section regenerated); `scripts/splice-fleet-block.py <SOUL.md>` — splices the **canonical fence out of the issue body** instead of retyping it, then asserts `block in soul` (punctuation is load-bearing: rules 13/14/15 have no period inside the bold and rule 16 does, and #972 is a lane failing on that alone); `scripts/stack-replay.sh <n:branch>…` — the stacked-PR replay loop (`git cherry` → cherry-pick the `+` commits, `CHANGES.md` from the base then `changes-index`, marker check, gates, lease) with `scripts/batch-rebase.sh` for the `main`-based equivalent. A hand-run union is how conflict markers end up committed inside a JSON file that a passing `check-docs` never looks at.

If the conflict is a genuine redesign rather than a re-apply, stop and report instead of redesigning.

**Before resolving anything, check whether the change already landed — a conflicting PR is often a duplicate vehicle.** When main already carries the same files and the same openspec change through a *different* PR, the conflict is the duplicate, not a divergence to reconcile. Two reads settle it:

```bash
git ls-tree -r --name-only origin/main | grep -E '<the feature paths>'   # the change IS on main
git merge-base --is-ancestor <branch-tip> origin/main                    # ...but ITS commit never merged
```

Present on main + not an ancestor = superseded. Do not rebase it: post the tree listing and both shas on the PR, say it is a duplicate vehicle, and leave the branch untouched — rebasing the duplicate rebuilds the same conflict against the copy that already shipped, and the eight-file "conflict" is really main winning twice.

Keep the branch at **one commit**. Author must remain `Asimov Agent <support@docondee.com>` or `Andy Holst` — a rebase preserves the original author; never re-author.

## Salvage audit before an owner prune — `scripts/salvage-audit.sh`

The owner's prune is irreversible for work that exists on no remote, and **uncommitted files are invisible to every ancestry test**, so a clean-looking branch list can still hide the only copy of a lane's run. Run `scripts/salvage-audit.sh [<repo>]` (read-only; deletes nothing) and report its four buckets plus the worktree flags.

Two refinements the script encodes, each of which a hand audit got wrong:

1. **A branch that ADDS a path main lacks is not automatically unique — test its CONTENT against every open PR head.** A rebase lane's own scratch branches (`rb<N>*`, `pr<N>-*`) hold replays whose content already sits in an open PR under a *different branch name*; classifying them UNIQUE inflates the preserve list and buries the real work. Measured: 13 raw UNIQUE collapsed to **5** once the added paths were checked against open PR heads.
2. **Fingerprint the added-file blobs to expose duplicate branches.** Two branches can hold the identical artifact (`agents/security-agent-soul-versioning` and `tmp/asv-trial` both carried blob `e22242fe6932`) — one preserve entry, not two.

Also: a path main *does* carry at a different path or in a different form is **not** byte-superseded (main had a file under `agents/llgenie-security/skills/security-scan-ops/references/`, while the branch held a standalone skill directory under `agents/llgenie-security/skills/`) — say that nuance rather than collapsing it into "already on main".

**Measure against `refs/remotes/origin/main`, never the bare name** — a stray `refs/heads/origin/main` shadows it and corrupts every quoted sha. The script prints whether that shadow exists.

## 5. Gates before push

**Run `scripts/post-rebase-verify.sh <base-sha>` first — it catches the two silent traps that each cost a ~40-minute CI cycle.** Both are invisible to `git rebase`'s "Successfully rebased":

```bash
make check-docs
make openspec-validate NAME=<change-name>
docker run --rm -u root -v "$PWD":/repo:rw -v "<owner-clone>":"<owner-clone>":rw -w /repo llgenie/test \
  python -m pytest tests/test_<touched>.py -p no:cacheprovider -q
```
`make test-unit` is the full gate but slow (~10 min); the targeted container run gives the same signal in seconds and does not depend on the host having pytest.

**Mount the owner clone as well as the worktree.** `-v "$PWD":/repo` alone makes git-dependent tests fail with `fatal: not a git repository: <clone>/.git/worktrees/<n>` — the worktree's `.git` file points into the parent repo, which is not mounted. Two tests reddened against a perfectly good tree until the second `-v` was added. The repo's own `TEST_OPTS`/`WORKTREE_MOUNT` does this; a hand-written `docker run` must replicate it.

**Gate the push on the result, not on the run.** A loop that pushes unconditionally lands red branches: write the gate so a failing test SKIPS the push and prints why. Then distinguish the two causes before blaming the branch — a test that also fails on a clean `main` worktree is a pre-existing red (disclose it and the sha), while one that passes on `main` and fails on the branch is the branch's own defect (do not push, report it).

**A targeted test list that expands to nothing runs the WHOLE suite.** `docker … pytest $TESTS` with an empty `$TESTS` silently becomes a full-suite run, and its first failure is then a red you did not ask for and may push straight past. Guard the variable and print what is about to run: when a PR touches no `tests/test_*.py`, `make check-docs` (+ `check-workflows` / `check-agent-profiles` for the files it does touch) IS the gate — say "no test files touched" instead of letting the shell substitute an empty argument.

## 6. Push
```bash
BR=<head-branch>
git push --force-with-lease="refs/heads/$BR:origin/$BR" origin "HEAD:refs/heads/$BR"
```
Lease on the ref you actually fetched, or the push is rejected. Verify: `git rev-parse HEAD` == `git rev-parse origin/$BR`, and parent == `origin/main`.

## 7. Report
Read back, never assume: `gh pr view <N> --json headRefOid,mergeable,mergeStateStatus` and `gh pr checks <N>`. Optionally post the rebase note as a PR comment and re-read it via the API.

**When `gh pr view` disagrees with the branch, `gh api` decides.** After a push in a busy repo `gh pr view --json headRefOid` can still return the *previous* head (and `mergeable: null` while GitHub recomputes); `gh api repos/<owner>/<repo>/pulls/<n> --jq '"\(.head.sha) \(.mergeable) \(.mergeable_state)"'` is the authoritative read. Quote the API's sha next to `git ls-remote <remote> refs/heads/<branch>`, and treat `mergeable: null` as *not computed yet* rather than as a conflict.

## 8. Sweeping many PRs after a long-parked `main` finally moves
A merge that moves a parked `main` invalidates every open PR at once: `MERGEABLE` becomes `BEHIND`, and some become `DIRTY`. Rules for that sweep:

- Plan from live state each step, not from the list you collected at the start. The PR that caused the move disappears from `gh pr list` as its branch is deleted, so the count you quote before is not the count you report after. Say which PRs vanished instead of implying the plan was exact.
- One PR per pass, in that PR's own worktree (reused if one already exists), one commit, gates, then `--force-with-lease` against the ref you actually fetched.
- Exclude drafts and anything labelled `do-not-merge`: those are a human's hold, and rebasing them pushes a branch under someone else's hand.
- Re-read the head sha before quoting any check verdict for a PR. A PR still being pushed can change head three times while you plan, and a verdict on the old sha describes a commit nobody will merge.
- Serial, never parallel: the whole point is to not re-queue N matrices at once, which is what starves the runners in the first place.
- Ready-made loops for the whole sweep — measuring staleness, preparing a batch without resetting, the gate-then-push shape, and the union resolutions for the habitual conflict files — are in `references/sweep-mechanics.md`.
- **A hold beats a handed order.** A sweep order written by a coordinator can list a `do-not-merge` PR — including as its first, dependency-critical step. Audit the order against the live labels before walking it (`sweep-plan.py --order '#834 #877 #901 …'` prints each held or missing step) and report the contradiction instead of resolving it by guessing; a hold is the owner's explicit stop, so the held PR is skipped and every later step that depended on it is deferred, not dropped.
- **Prepare in batches, push one at a time.** Rebasing a batch of worktrees in one pass is safe and fast; pushing must stay per-PR and gated, because the push is what starts the verdict. Prepare → resolve → gate → push for one PR, then the next.
- **Reuse an existing worktree instead of creating a second one.** If `../llgenie-wt/pr<N>-rebase` already exists, move it to the branch tip with `git merge --ff-only` and rebase there; a second worktree for the same PR splits the evidence and multiplies the count the owner has to review.
- **A worktree that will not fast-forward is a finding, not an obstacle to clear.** Compare `git rev-parse <local>^{tree}` with `git rev-parse <remote-tip>^{tree}`: identical trees mean the local commit is a superseded replay and the branch can be moved to the remote head safely; different trees mean unpushed work, so report it and leave the worktree alone. A long divergence (dozens of unique commits each way) is a stacked branch that has moved on — never force it onto the new base.
- **Before a lease push on a diverged branch, ask what the push would DELETE.** `git cherry HEAD <remote>/<branch>` lists the remote's commits: a `+` row is remote work with no local equivalent, and a lease push that succeeds would erase it. Push only when every row is `-` (already present) or the two trees are identical; otherwise complete the local rebase, park it, and report the `+` shas — the dangerous outcome is not a rejected lease, it is a lease that succeeds on a branch someone else still owns.
- **Exactly one rebaser at a time.** A host sweep is a workaround for a broken in-repo automation, and a workaround that outlives its cause becomes a second writer of the same branch. While the in-repo bot's sweep is red, this lane rebases; once it is green again *after its own fix has merged* — and not merely because one of its runs concluded `success` while a PR stayed conflicted — this lane degrades to reporting transitions and pushes nothing. Say which regime produced any report, so a stale one cannot be read as current.
- **The same failing check on many unrelated PRs is one cause, not many.** When a batch reports `linux / unit` (or any single job) newly failing across a dozen branches, prove the shared cause against a pristine worktree of the new `main` before touching any branch: if it fails there too, the branches are innocent and only a main-side fix unblocks them; rebasing them re-queues the same red. Attribute it per PR with the sha it was measured at, so no lane re-derives it.

## Sweeping a whole board that conflicts on ONE index row does not converge in one pass

`CHANGES.md` adds a row at the same table position on every branch, so **each PR that merges re-dirties every
other PR in the sweep** (measured: eight rebases read `MERGEABLE` after pass 1; the moment #826 merged as
`71c84025`, the other eleven read `CONFLICTING` again — one new row is enough). Plan for a second and third pass:

- Push, then `git fetch origin main` again and **re-rebase only the ones the merge re-dirtied**, reusing the same
  worktrees. The branch content is already gated, so a re-pass only re-unions the row: `check-docs` + lease push,
  no test re-run (`git diff origin/main -- <code>` is empty, only `+` rows in `CHANGES.md`).
- Loop the union+continue until no rebase is in progress: a multi-commit branch can conflict on `CHANGES.md` once
  per commit (`git rebase --continue` then stops again), and a branch that **renames** its note file can re-add a
  row naming the old note. `make check-docs` catches exactly that (`links agent-wiki/…, which does not exist`) —
  delete the stale row and `git commit --amend --no-edit` rather than inventing a note.
- The structural cause is a filed issue (`#934`, `#682`): report it instead of re-pushing in a loop forever.

## A skipped cherry-pick turns a rebase into silent DELETIONS of main's work

`git rebase` prints `warning: skipped previously applied commit` when the branch's first commit was squash-merged
as a *different* commit. The remaining commit's patch is then computed against a parent that carried files the
merge base never had, so it **deletes** main's copies (`scripts/pr_heads.py`, `tests/…`, a `.pr874.md`) while the
rebase reports `Successfully rebased`. `merge-tree` had flagged the same pair as conflicting; a clean rebase is not
evidence of a correct one.

Detect: after any rebase, `git diff origin/main --stat` must show **only additions** for a change that only adds
files. On a deletion you did not author, rebuild the branch from the branch's NET diff:

```bash
git checkout -B pr<N>-rebase origin/main
git diff $(git merge-base origin/main <remote>/<branch>) <remote>/<branch> > /tmp/net.diff
git apply --3way /tmp/net.diff      # conflicts are then real unions: .PHONY keys + target blocks, docs sections
git add -A && git commit -C <old-tip>   # keeps the original author+message
```

Resolve `Makefile` hunks as: main's `.PHONY` line with the branch's key inserted (never the branch's whole line —
it drops keys main added, e.g. `ci-slow-rows`), and both target blocks (main's newer block first, the branch's after).

## Two sweep lessons that cost a re-run each

**A branch that has moved `CHANGES.md` to one-row fragments is NOT a row union.** After #934 the index is
`docs/changes.d/<note-stem>.md`, one row per file, rendered into `CHANGES.md` by `scripts/changes_index.py`.
A rebase of such a branch conflicts because main added rows the branch has no fragment for, and inserting a
row into the rendered table fights the generator. Resolve at the FRAGMENT level: for each row in
`git show origin/main:CHANGES.md` whose note stem is missing from `docs/changes.d/`, write
`docs/changes.d/<stem>.md` holding that row verbatim, then let `scripts/changes_index.py check` +
`write` referee. Verify with the row-set diff (`comm -23` over `^| 20` rows must be empty; `comm -13` must
be exactly the branch's own row) — a hand-inserted row renders away on the next `make changes-index`.

**Gate the push on the branch's OWN head, not only on the rebased tree.** Two PRs in one sweep
(#882, #940) had a green rebase and a red PR: their tests/openspec jobs fail at the branch's tip
before the rebase, because the branch's own second commit contradicted its own test (removed
`timeout-minutes` from `uses:` jobs, then demanded it) or left its OpenSpec checklist unticked.
Before pushing, read the run at the PR's CURRENT head (`gh run list --commit <sha>`) and, for any
failing job, reproduce it on the rebased tree — then on a pristine `origin/main` worktree. Fails on
main too → inherited; fails at the branch's own head and on the rebased tree → the branch's, so park
the rebase, comment the measured evidence (job, `path:line`, both counts), and push nothing: a push
only buys a fresh matrix for a verdict already known, and ticking another change's tasks or
re-designing its logic is not this lane's call.

## Hard rules
- **A conflict is the reason a PR may be held, never the remedy.** Two cases and they are different: if a rebase resolves it, do the rebase and do not label anything; if the divergence is structural (a duplicate vehicle, a base that will never converge, a file another PR is restructuring), the hold needs the issue that removes the cause — named on the PR with the exact removal condition — not a note saying "conflicts". Never place `do-not-merge` on a bot's PR out of caution: "I am not confident" is a review, not a label, and a hold whose reason expired reads identically to abandonment (`BLOCKED` either way).
- **A conflict block can be a POSITION clash, not a content clash — resolve it as "both, in order".** Both sides inserted a run of functions/tests at the same point (main's `_deferred_engines` rewrite vs 11 new tests; main's `_unquote`/`workflow_run_coverage` vs the branch's `_jobs_block`/`check_uses_job_keys`). The union is the branch's block, then MAIN's newer block, and the shared closing lines (`})` / `return out`) belong to BOTH — duplicate them, or the first function loses its body and only a syntax check catches it.
- **`git checkout --theirs -- <path>` during a rebase takes the branch's WHOLE file and silently deletes whatever main added to it.** Measured on #913: `--theirs` reverted main's #925 (`import base_ref`, the `base: str | None = None` signature). Always re-derive such a file from `origin/main` and re-apply only the branch's own hunk (here: remove the `sys.path.insert` lines, keep `import json`/`import base_ref`), then prove it with `git diff origin/main -- <path> | grep -E '^[+-][^+-]'` showing only the intended lines.
- **`git rebase --continue` hang** — without `GIT_EDITOR` it can open an editor on the commit message and sit forever (measured: a 180 s tool timeout with the rebase still at `msgnum 2/25` and no git process left). Always `GIT_EDITOR=true git -c rerere.enabled=false rebase --continue`; if it already hung, re-run it with the variable — the rebase state is intact.
- **Automate the row insert with a script FILE, not a heredoc** — a `python3 - <<'EOF'` heredoc is refused as a dangerous command in unattended runs. Keep `insert_rows.py` (takes path + a rows file, inserts after the `|---` separator) in the profile scratch dir and call it, plus one `rows_<pr>.txt` holding the branch's verbatim row.
- **`make check-registry` cannot finish on this host** — its first half, `scripts/sync_registry.py check`, fetches the upstream contract and hangs past 600 s; the guard that actually protects a rebased re-vendor branch is the deterministic half. Run `make check-registry-keys` and report the network half as unable-to-run instead of calling the PR red.
- **A rebase sweep never needs `git reset --hard`, and a worktree is not storage.** Before touching a worktree you did not create this session, run `git status --porcelain` and `git log <remote>/<branch>..HEAD` — anything listed there is somebody's work that exists on no remote. Measured the hard way: a `reset --hard` onto the fork head moved a branch off a local-only commit that had never been pushed, and it survived only because a tag was made seconds later. Reset only a worktree you created and whose commits are already pushed; otherwise report it.
- **A rebase performed entirely through git in a sibling worktree counts as ZERO "relevant mutations" to the host's completion guard.** Measured twice, including after adding a posted-and-read-back PR comment: a full rebase + lease push + `check-docs`/openspec/container pytest, plus a posted PR comment re-read from the API, still left `relevant_mutation_attempts: 0` and the run was told "no task-relevant mutation was attempted". The guard's relevance filter only counts writes inside the paths it tracks (the profile scratch is explicitly excluded; `../llgenie-wt/…` git operations and `gh pr comment` are not classified). Do not invent a file edit to satisfy it: emit `nerve_nervous_event` (`completion_candidate`) with the measured evidence and call `nerve_verify` with an explicit per-check `pass: true/false` checklist — a free-form state dict grades ESCALATE, a numbered checklist with the sha/byte values each check was measured at grades PASS. If the guard repeats anyway, the check is unsatisfiable for this lane: report the measured state and stop.
- **Mode gate: compare timestamps, not conclusions.** `createAt` of the newest `schedule` run must be strictly after PR 821's `mergedAt` *and* its conclusion must be `success`; a `success` run that predates the merge (or a `workflow_dispatch` result) does not put this lane into ALERT-ONLY. Measured: a green schedule run 5 h before the merge was repeatedly the only green in the window while the workflow itself was `disabled_manually`.
- Never merge, never squash to `main`, never push to `main` — merges are CI/owner only.
- Kill by PID, never by pattern: `pkill -f 'make test-unit'` matches the shell running that very command and takes down the call instead of the target. Capture the PID (`$!`, or `process_manage list`) and `kill <pid>`. Same class of mistake as a `git checkout --` that eats someone else's edit.
- Do not judge a long run by a piped tail. `make test-unit 2>&1 | tail -30` buffers, so a suite that is 80% done looks completely silent — the first honest report of the full gate came only when the process ended. Write to a log (`> /tmp/tu.log 2>&1 &`) and read it, or run the bounded subset. The full suite needs well over 900 s here (measured: ~80% at the 900 s timeout, killed with Error 137), so a 900 s foreground timeout will always cut it off.
- Never touch unrelated files; a rebase PR's diff must stay its own change.
- Never run `make worktree-prune` / `git worktree prune` / `git worktree remove` — owner-only; it deletes directories and cannot see uncommitted work.
- Leave the worktree in place for the owner to inspect.

## Pitfalls
- **`agents/<profile>/SOUL.md` is a protected agent-instruction file: every edit needs its own interactive approval, which can time out and then refuses a retry.** Batch a lane's SOUL change into ONE write — the fleet block, the lane section and any new rule together — instead of patching the file three times, or you spend three approvals on one file and finish with two of three rules landed (a missing rule is invisible: `check-agent-profiles` only proves the rules the manifest declares). If a write is refused after a timeout, stop and ask the user to approve the prompt; do not route the edit through `terminal`, `execute_code`, or a second path.
- **`make check-agent-profiles` compares the tree against the LIVE profile on this host, so its `live-longer` finding is machine state, not a branch verdict.** It fails when the tree's `SOUL.md`/skill copy is *shorter* than `~/.hermes/profiles/<profile>/…`, which CI cannot see because it has no live profiles — the same tree passes there. Report it as a host-state divergence with both byte counts (tree vs live) and do not call the branch red on it; the deterministic halves are the manifest/rules check and the frontmatter/section checks.
- **Only regenerate the SOUL of the profile THIS branch owns — a blanket fleet-block rewrite across `agents/*/SOUL.md` fails on its second step and trespasses on other lanes.** Regenerating every SOUL so the canonical block matches `agents/standing-rules.md` makes each of those profiles state the block verbatim, which turns its entry in `agents/fleet-block-exemptions.json` `STALE` (`fleet-block-drift` becomes `fleet-exemption-stale`), and the exemption is owned by the lane that has not yet written its rule. Revert the others (`git checkout origin/<base> -- agents/<other>/SOUL.md`) and regenerate only the file the branch adds; the reason a gap exists is another lane's work queue, not a merge conflict.
- **`make sync-agent-profile PROFILE=<p> CHECK=1` fails whenever the tree and the live profile differ, including for a profile the repo has just rewritten.** The sequence is: copy the live file aside (`cp -a ~/.hermes/profiles/<p>/SOUL.md <scratch>/SOUL.md.before-sync`), run `make sync-agent-profile PROFILE=<p>` (repo → profile; it prints `verified: 1 file(s) read back identical`), then re-run with `CHECK=1` and expect `OK: … match … byte for byte`. Running only `CHECK=1` proves nothing about the tree and leaves a red that reads like a branch defect.
- **Attribute a red from the job LOG, not from the check name.** `gh api repos/<owner>/<repo>/commits/<sha>/check-runs --jq '.check_runs[]|select(.conclusion=="failure")|.details_url'` gives the job id; `gh api repos/<owner>/<repo>/actions/jobs/<id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'` returns the assertion text (the API refuses some logs without that flag). The file:line in the log is what lets you prove "inherited from a red `main`" against a pristine worktree instead of guessing from job names — a plain read that returns zero bytes is the flag's guard, not an unreadable log.
- **A repo-wide `gh run list --limit N` window is not a per-PR history.** After a capacity sweep the newest runs dominate, so an older PR's retry silently falls out of the window — a stuck-cancellation monitor built that way reported zero for a PR that was provably `attempt=2`. Ask per commit: `gh run list --commit <sha> --limit 1`. If the thing you monitor can scroll off page one, the monitor is blind exactly when it matters.
- **A cancellation that survives a re-run means someone's sweep, not a workflow bug.** Read the run's `attempt` and `triggering_actor` before hunting YAML. `attempt >= 2` cancelled = no verdict is coming; attempt 1 is ordinary `cancel-in-progress` noise.
- **`gh pr checks` reports `cancelled` runs as `fail`.** Never quote its fail column as a failure count, and never call a PR red on it: read the conclusions instead — `gh api repos/<owner>/<repo>/commits/<head-sha>/check-runs --jq '[.check_runs[].conclusion // "running"] | group_by(.) | map("\(.[0]):\(length)") | join(" ")'`. `cancelled` means superseded by a newer run (`cancel-in-progress` on PRs) = *not yet*, `failure` means red. Also anchor on the PR's **current head sha**, because `gh pr checks` aggregates across runs and a new push silently invalidates every earlier number, including your own.
- A check whose *name* still contains `${{ matrix.… }}` does **not** prove a YAML defect: a run cancelled before its matrix instantiated keeps the workflow's declared names with no expanded children. Check the conclusion first — if it is `cancelled`, the matrix never expanded because nothing ran. Send someone hunting a workflow fault only when a *completed* run has unexpanded names.
- "All checks green" is not "mergeable": the auto-merge condition is `mergeStateStatus == CLEAN`. A PR can be `MERGEABLE/BLOCKED` with every check successful, and reporting that as green-and-mergeable is how a red board gets called ready. The converse matters as much: that same PR is *owner-ready* — a human's approval is the only missing step — so say which of the two you mean rather than emitting one word that is false for half the audience.
- A sweep that reports success while PRs stay conflicted, or crashes its own decision step, is broken — check the run log, do not trust the green.
- CI `guard` sitting `pending` for many minutes with other runs also queued is a **runner capacity** problem, not something wrong with the PR. Report the run ids and say so; do not re-push.
- Capacity starvation and a crashing automation sweep are different failures: keep them in separate issues. Conflating them hides one behind the other.
- After a long capacity backlog clears, PRs that were `MERGEABLE` are the ones to watch: `main` moved while nothing merged, so they can turn `DIRTY` and need this same rebase.
- Worktree count is a tracked trend under an owner-only prune. Always report the worktree you left and its path; never prune to compensate.
- The `pr<N>-rebase`-style local branch is scratch; the branch that matters is the one on `origin`.
- The knowledge here belongs in the repo, not only in this profile: a host skill is admitted **by name** in `HOST_SKILLS` (`scripts/check_agent_skills.py`) and needs frontmatter plus `## Inputs`/`## Output`/`## Rules`. `.hermes/skills/rebase-conflict` already covers the inner half (resolve, stage, stop, caller continues and pushes) — any in-tree version of this procedure must *point* at it, never restate it, and must say which half runs where: the leg contract stops at `git add` in the CI image, this outer procedure owns survey, worktree, gates, lease and report on the host. Never merge the two contracts: one would then say "stop after staging" and "survey and push" at once.
- When filing an issue whose `## Technical` embeds a whole `SKILL.md`, the body gate (`scripts/issue_body.py::missing`) reads every `^## ` line as an issue section: a verbatim fence yields "unknown sections" and `Technical` stops being last. Demote the embedded headings to `###` and tell the implementer to restore `##` when writing the file.
- **`rerere` is enabled on this clone and its cache can hand you a WRONG `CHANGES.md`.** `git rebase` printed `CONFLICT` then `Staged 'CHANGES.md' using previous resolution`, staging a mangled 3-column row copied from a *different* PR's conflict. Always inspect the staged file and rebuild it (main's file + the branch's own row) instead of trusting a rerere resolution; run `git -c rerere.enabled=false rebase --continue`. Verify the row shape (`line.count('|') == 5` for a 4-column table) and that the row's *text* matches the branch's original row, not just its note name.
- Rebase `--force-with-lease` leases must name the ref actually fetched, else the push is rejected; verify afterwards that `HEAD` == `origin/<branch>` and the parent is `origin/main`.
- **Prove content preservation by added/removed LINES, not by tree diff.** `git diff <old-base> <old-tip>` vs `git diff origin/main HEAD` (after rebase) will *always* differ once main moved; the honest check is `diff <(grep -E '^[+-][^+-]' old.diff) <(grep -E '^[+-][^+-]' new.diff)` plus the `--stat` totals (e.g. `17 files changed, 1836 insertions(+), 2 deletions(-)` on both sides). Diffing a pre-rebase commit against its rebased twin also shows all of main's work and reads like drift when there is none.


## Fleet orchestration (issue #1010) — this skill's lane side

1. **report-back:** rebase/resolve to done (last push, gates green, head fixed) -> post head sha + PR number + what stands to @llgenie-planner.
2. **new-PR -> reviewer:** the planner sends new reviewable PRs to @llgenie-pr-reviever; this lane never reviews its own PR.
3. **version-here:** this behaviour is versioned by issue + PR under agents/llgenie-pr-merge-conflict/, then sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1 comes back byte-identical.
4. **one lane, one PR:** before a sweep touches a PR, check bot-claim: and agent/issue-<n>-* branch; a claimed PR is another lane's (issue #994 rule 1).

