# Fixing a red PR and rebasing onto a moved main

## The close gate reads BOTH the joined commit messages AND the PR body

`make check-pr-closing` requires an *adjacent* close (`closes #N`, nothing between the keyword and the number) in the squash text (the joined commit messages) AND in the PR body, and the **two close-SETS must match exactly**. A branch can "claim" an issue without closing it: ANY issue token in a commit subject or the PR body registers the issue as claimed — `(#N)` bare (a `fix: … (#1694)` subject), `(issue #N)`, `Issue: #N`, `references #N` — so the gate reports a `squash-mismatch` when the commits carry no adjacent close for every claimed issue. A multi-commit stack that closes `#1558` in one commit and merely *claims* `#1694` in another therefore needs the body to close `{1558,1694}`, both of them, or it reds on the set mismatch.

- Diagnose against the real script at the PR head — it can be a newer revision than `main`'s copy. The check prints `claimed={...}` vs `body_closed={...}` vs the commit-side closes; compare them.
- Fix WITHOUT rewriting history: add an additive marker commit whose message carries the adjacent close (`...\n\ncloses #N`). Verify with `make check-pr-closing` locally, push, and the guard step goes green.
- **Equally valid when the branch is a single-purpose stack: AMEND the head commit message** to append `closes #N`, then force-push with lease. Amending a message only does not change the TREE, so an already-dispatched engine-build producer at the old head is still valid proof (diff the trees to confirm identity before citing it) — but the amend creates a NEW head sha, and `engine-build-pr-trigger` only dispatches at the pushed head, so a fresh producer appears (queued for some minutes) at the new sha while the old one drains; watch for the new one and quote IT as the proof. Do not rewrite commits just to land a message-only fix when an additive marker commit is enough.
- A body that names a PR (`references #<pr>`, `supersedes #<pr>`) instead of an issue still reds: the gate wants an issue the squash text can close. The remedy is to FILE the tracking issue for the rule the change enforces, then add an adjacent `closes #<issue>` to the body — do not point the token at another PR, and do not drop the AGENTS/BASE header lines while editing the body.
- The same branch can red on several gates in sequence: after the close gate, the guard's next step may be `check-pr-base` — fix both before re-pushing or you get a second round-trip.

## `check-pr-agents-line` reads the PR BODY, and a body edit does not retrigger CI

`make check-pr-agents-line` requires two exact header lines in the PR body — `AGENTS: <sha> <bytes>b <lines>l` (the rulebook the author read) and `BASE: <sha> (== origin/main at open)`. Take them from `make bot-preflight` output verbatim: rewriting the regex, re-wrapping, or hand-editing the byte/line counts breaks the gate.

- Editing the body changes no commit, so **no CI run starts**: the runs already keyed to that `head_sha` stay red indefinitely. The guard reads the live body (not the run's snapshot), so trigger a fresh evaluation — push any commit, or `gh run rerun <run-id>` — then confirm the new run's guard job is green. Do not report a body fix as verified on the strength of the edit alone.
- Batch body-only gates before the last push. A body fix discovered after the run already failed costs a second full CI cycle, and a body fix plus a tree fix found together (lint, agents-line) belong in ONE amend + push.

## A PR body's prose citations go stale on every amend — re-read and update them

The AGENTS/BASE lines are not the only body content that carries a sha: a Verification section
saying "the suite is green at head `<sha>`" pins the head at write time, and every later amend or
force-push silently makes that sentence false while all four gates still pass (they check the
AGENTS/BASE lines and the close set, not prose). Before reporting a PR reviewable, diff the body's
cited shas against the live head:

```bash
gh api repos/O/R/pulls/<n> --jq .body | grep -oE '[0-9a-f]{8,40}' | sort -u   # every sha the body names
gh api repos/O/R/pulls/<n> --jq .head.sha                                   # the only one that may appear
```

Fix with `gh pr edit <n> --body-file /tmp/body.md` (heredoc-built file, then read the body back).
The edit does not retrigger CI, and the body-reading guards are not invalidated by it — but re-run
them against the fresh live body anyway, so "the body is correct" is measured, not assumed.

## A make gate target silently IGNORES variables it does not declare

Make passes every `VAR=value` on the command line into the recipe's environment, so a gate invoked with
the wrong variable names still RUNS on its defaults and exits 0. That green proves nothing about the
thing you meant to test. The close gate declares `PR_BODY` (body file), `PR_BRANCH` (head ref) and
`PR_BASE`; it has no `PR=` or `REPO=` variable, so `make check-pr-closing PR=<n> REPO=O/R` validates
only the commit side of whatever HEAD is checked out.

- Before running a gate about a PR, read the recipe: `grep -nA3 '^<target>:' Makefile`. Pass exactly the
  declared variables (`PR_BODY=body.md PR_BASE=origin/main`) so the half you changed is inside the input.
- Green-with-wrong-inputs and green-with-right-inputs look identical from the exit code; echo the
  command line and its rc in the same call that runs it.
- The body half needs the LIVE body: `gh api repos/O/R/pulls/<n> --jq .body > body.md` immediately before
  the check, or the gate validates a stale local copy.

## `check-pr-sync-line` misattributes a FOREIGN `agents/` change that landed on main after your base

`check-pr-sync-line` reds claiming "this PR changes `agents/<profile>/` — add a `SYNC:` line" for a PR whose own diff touches **no** `agents/` path at all. The gate diffs head against **LIVE** `origin/main`, not the PR's merge-base, so any `agents/<profile>/` change another PR landed on main AFTER your declared base is folded into your diff-scope and blamed on you.

- Confirm the misattribution before touching the body: `git diff <your-declared-base>...HEAD --name-only | grep '^agents/'` — empty output means the `agents/` change is NOT yours. Cross-check that live main advanced past your base since you cut it (`git log --oneline <your-base>..origin/main -- agents/` names the foreign commit/PR).
- **Do NOT "fix" it by adding the demanded `SYNC:` line.** That conserves a phantom: a `SYNC:` line on a PR that made no profile change is noise the drop-rule conservation later re-reads as a live-edit, and it does not clear the root cause (the gate still diffs live main).
- The real remedy is the same as the base gate's: **rebase onto the current tip** so the merge-base == `origin/main`, which collapses the diff-scope back to your own changes and clears `check-pr-sync-line` and `check-pr-base` together. See the base-gate section above for the fetch/onto recipe.
- **The `SYNC:` line is ANCHORED end-to-end — nothing may follow the profile name.** The parser is `^SYNC:\s+(\w+)\s+make sync-agent-profile PROFILE=\1\s*$`, so a helpful trailing parenthetical — `SYNC: <profile> make sync-agent-profile PROFILE=<profile> (verified locally)` — breaks the `\s*$` tail and the gate reds exactly as if the line were missing. Emit the line bare: `SYNC: <profile> make sync-agent-profile PROFILE=<profile>` and nothing after it.
- A `SYNC:` line on `references #<pr>`/`supersedes #<pr>` still reds — the gate wants an issue. But a PR with no real `agents/` change needs no `SYNC:` at all once rebased; do not invent one to satisfy a phantom.

## A merge burst drifts the base repeatedly — cap the rebase cycle, do not loop it

When several lanes land PRs back-to-back, `main` can advance four or more times inside a single ~14 min
`linux / unit` suite, so every rebase is stale again before its run concludes. The signature is stable and
recognisable, and it is NOT a defect in the branch:

    [check-pr-base] foreign commits (1):
    [check-pr-base] measured against `origin/main` at `<a sha newer than your rebase point>`
    make[1]: *** [Makefile:1108: check-pr-base] Error 1
    make: *** [Makefile:1810: ci-unit] Error 2

- **Confirm it is drift, not your change**: the rebased diff is your own files plus a `CHANGES.md`
  refragment, and the drift sha advances on every cycle without a file conflict. If the diff grows any
  other file, it is scope, not drift — read it before rebasing again.
- **Predict the churn instead of absorbing it**: check the sibling PRs that will move `main`.
  `mergeStateStatus=BLOCKED / reviewDecision=REVIEW_REQUIRED` on them means they will NOT land under your
  run and the next cycle can be clean; a sibling mid-CI means main will move again. Read that BEFORE
  spending another suite.
- **Cap the cycle at two drifts on the same PR.** Past that, the honest state is "blocked on fleet merge
  traffic": report the live head, the drift sha, the proof the suite itself is green, and one final rebase
  when the burst settles — rather than a third and fourth 14-min cycle. Repeated full-suite cycles against
  a moving main burn the fleet's slots and read to the user as an unfinished task.
- **Report it in ONE answer when asked for status.** "Done" is: what changed, the live PR head sha, which
  check is red and the exact gate line proving it is drift, and what you are deliberately not doing. A
  state report of "blocked on fleet merge traffic" is a finished report; an uncapped silent retry loop is
  not, and the user reads a long silent wait as work that never delivered.
- **Never fold a body-gate red into a drift cycle.** The AGENTS/BASE/SYNC lines are front-loaded at PR
  creation precisely so a drift rebase is the ONLY round-trip left; a body line discovered mid-churn costs
  a whole extra cycle that the drift will then invalidate anyway.

## The base gate reds when main moved past the branch base

`make check-pr-base` fails when the branch's merge-base is no longer the base it was cut from (main advanced). The gate is wired to the **LIVE** `origin/main` ref (ci.yml runs `git fetch origin main` first, then compares `merge-base origin/main HEAD == origin/main`) — so it reds on the NEXT push the moment main advances past the branch's rebase point, **even when there is no file conflict**. That red is a genuine base-currency defect the gate itself demands you fix: a rebase onto the current tip is owed, and this does NOT conflict with the fleet rule "rebase only when actually conflicting" — the gate makes the absence of a conflict irrelevant. Fix: `git fetch origin main` (explicit refspec, never the ambiguous shadow), rebase onto the freshly-read tip (retain any marker commit), confirm `git merge-base origin/main HEAD` == `git rev-parse origin/main`, and verify `make check-pr-base` before pushing. Quote the tip sha you rebased onto in your report — a sha quoted by a planner/DM is stale by the time you read it.

## A behavioural change under `agents/` reds `check-docs` until the change-note trio exists

`make check-docs` requires every behavioural change under `agents/<profile>/` (SOUL, skills, manifest,
provisioning folds) to ship **three** artifacts in the SAME commit — and it reads the **committed**
`base..HEAD` diff, so a note sitting only in the working tree is invisible and the gate stays red
until you commit it:

- `agent-wiki/<stem>.md` — the **prose** note (what changed and why).
- `docs/changes.d/<stem>.md` — a **single** markdown table row
  `| <date> | <desc> | [<stem>.md](agent-wiki/<stem>.md) | #<issue> |`. Not prose — the file is one row.
- `CHANGES.md` — **generated** from all `docs/changes.d/` fragments by `make changes-index`. Never
  hand-edit it; run the target to regenerate the table and commit the result.

The two note files are trivially swapped: prose goes in `agent-wiki/`, the one-line row goes in
`docs/changes.d/`. Copy the exact shape from a same-class precedent (`ls agent-wiki/ | grep <topic>`,
read its `.md` and its `docs/changes.d/` row) instead of inventing the format. Verify with
`make check-docs` AND `make changes-index` (idempotent) before committing — the gate names the missing
artifacts, and an un-committed working-tree note is the usual reason it still reds after you "added" it.

## A CHANGES.md conflict in a rebase resolves by regeneration, not by hand-editing markers

`CHANGES.md` is generated from `docs/changes.d/` fragments by `make changes-index`. When a rebase conflicts on it (both sides add a row to the shared index), keep BOTH sides' fragment rows, drop the conflict markers, then run `make changes-index` to regenerate the table from all fragments. Never hand-merge the generated table — the regenerated file is the source of truth and drops the markers for you.

## An openspec `tasks.md` add/add conflict: keep the ticked head state

On an openspec `tasks.md` add/add conflict, keep the tick state that is correct for the branch head — already-verified boxes stay `[x]`, genuinely-pending boxes stay `[ ]` — then `git add` and continue the rebase. Do not blanket-flip boxes to resolve the conflict.

## A live→tree profile fold is not a pure copy: check-docs wants the change-note trio, and a missing trailing newline reds ci-lint

When folding live-only host files into `agents/<profile>/` (the #1724/#1060 live→tree remedy), the fold is a **behavioural change** to the tree, so `make check-docs` (issue #1123) requires a change note: `agent-wiki/<stem>.md` (prose) AND `docs/changes.d/<stem>.md` (the single `| row |`) AND the `CHANGES.md` row — which is **generated** by `python3 scripts/changes_index.py write`, never hand-edited (the file says so). The note+row must be **committed** in the same PR commit: check-docs reads `base..HEAD` for changed paths, so an untracked/stray note is invisible and the gate reds `adds no agent-wiki/<stem>.md note`. Copying a live file verbatim can carry a missing trailing newline → reds `ci-lint`; run `make lint` in the worktree before committing (`printf '\n' >> file` + `git commit --amend`). After folding, the only acceptable remaining `check-agent-profiles` rows are the benign tree-ahead (`live-lines-missing` = tree carries new lines a later sync delivers); my target state is absent-from-tree = 0.

## Arming auto-merge: only on a green head, and read the arm back; a push disables it

A merge is armed only when `check-runs` are **all** `completed/success` at the current head sha — never while a heavy row is `in_progress` (arming under a pending row would auto-merge a head its own CI has not blessed). `gh pr merge <n> --squash --auto` then **read `.auto_merge` back**: exit code is not the fact, and a push to the branch **disables** auto-merge (a head that moves after arming silently un-arms it — re-check `auto_merge` and re-arm only if the new head is green). The owner may arm a PR themselves (`auto_merge.enabled_by.login == andyholst`) — that is owner authority (#1088), do not un-arm or re-arm over it; verify their armed squash title/head are consistent and leave it unless a defect is real. Before arm, confirm the body-reading gates pass against the **live** body at the current head: `make check-pr-agents-line PR_BASE=origin/main PR_BODY=<live>`, `check-pr-sync-line`, `check-pr-closing` — a body edited after the push is read by a run that starts later (start_time > edit), so a fresh run is not stale-body, but you must run the gate yourself against the live body to prove it.

## A PR that only *cites* another issue must justify-open it, not close it

When the change resolves issue A but merely *records* or *reports on* issue B (an audit that files a
finding, a note that references a sibling), the gate reads the `#B` token as a claim and reds:
`[check-pr-closing] this change fixes #B but neither closes it nor says why it does not`. Do **not**
add `closes #B` — closing an issue your PR does not fix is a false close. Add the explicit justify-open
note instead, on its own line in the body:

    This PR does not close #B because it is a measurement-and-record change, not the fix …

The parser accepts a negated clause (`does not close #B`, `we do not close #B because …`,
`cannot close #B`) and any wording after `because`; the negation must be adjacent to the `#B` token it
excuses. The PR *title* naming `#B` is fine once the body carries the note — the token is only
resolving when nothing negates it. Verify locally before pushing:

```bash
python3 scripts/check_pr_closing.py check --head HEAD --base origin/main --body-file /tmp/body.md
```

and remember the body half only sees what you pass — pass the LIVE body, not a stale local copy.

## check-pr-closing wants ONE matching close set; a body edit does not retrigger CI

An agent PR body AND the squash commit text must adjacently close the SAME issue: subject `(#N)` is a claim, not a close — an adjacent `closes #N` is required, and a body `Closes #A` vs squash `closes #B` is a different-sets violation. `- AGENTS:` bullet prefix reds `^AGENTS:` (bare line only). A body edit does NOT key new CI on the same head — force-push a new (amended) head so the guard re-reads the corrected body, or POST `actions/runs/<id>/rerun-failed-jobs` to re-read the live body at the same head. The scope-guard's `make check-docs` step reads problem text live; its job-log can be 0-byte (documented pitfall) — re-run the job to unlock the line at completion.

## A rebase rewrites history, so the push needs a measured-lease force

After a rebase the branch tip is not an ancestor of the remote tip, so a plain push is rejected. Push with `--force-with-lease=<branch>:<sha read from ls-remote seconds ago>` plus `--force-if-includes`.

**`git rebase --onto <newbase> <upstream>` replays `<upstream>..<branch>` — pass the MERGE-BASE (the branch's old base), never the branch tip.** Passing the tip as `<upstream>` makes the range empty: git happily reports `Successfully rebased` and resets the branch to `<newbase>`, SILENTLY DELETING every commit on the branch. This is the exact form that bites: `git rebase --onto origin/main <current-head> <branch>` prints success and leaves the branch at `origin/main` with your work gone. Read `<upstream>` from `git merge-base origin/main <branch>` (or the base the commits sit on) and confirm afterwards that `git log --oneline` still shows your commits and `git rev-parse <branch>` is NOT `origin/main`. Recovery if you already ran it: the old tip is in `git reflog`/`git cat-file -t <old-sha>` (still a live object) — `git branch -f <branch> <old-sha>` then redo with the correct upstream.

**`git checkout -B <branch> <oldbase>` in the same command as the rebase empties the range too.** If you move the branch ref down to the merge-base first, `<oldbase>..<branch>` becomes empty and the rebase again "succeeds" by leaving the branch at `origin/main` with all commits gone — the ref-log recovery above is the remedy. For a **single fix commit** the safe recipe is not rebase at all:

```bash
git fetch origin main
git checkout -B <prep> origin/main
git cherry-pick <fix-sha>          # fix-sha = the commit that holds only your change
```

Cherry-pick either lands or stops with a real conflict; it never silently drops the commit. Verify after: `git log --oneline -2` shows your subject on top of the fetched main tip, and `git diff origin/main --stat` is non-empty.

**A conflict caused by a helper RENAME on main: adopt main's name, then prove the old name is gone.** Main can rename an internal helper between the branch point and the new tip (a streamed `_sh_live` folded into `_sh`, for instance), so your fixed hunk calls a symbol that no longer exists. Resolve by taking main's spelling in BOTH directions — the call site and any new helper you added — then assert it:

```bash
grep -c '<old_name>' <file>        # must print 0
grep -n '<<<<<<<\|=======\|>>>>>>>' <file>   # must print nothing
python -m py_compile <file>
```

Do not "keep the branch's spelling for consistency": the rebased commit sits on main, and main's name is the one that exists at runtime. A leftover reference to the old name is a `NameError` at the first build, not a style nit.

**The INVERSE holds when you land the fix on the BRANCH itself: keep the BRANCH's spelling there.** If main renamed a helper (`_sh_live`→`_sh`) AFTER the branch point, the branch's tree still carries `_sh_live`, so a fix built on main conflicts on that symbol and a resolution that takes main's `_sh` is a `NameError` on the branch. Resolve to the branch's CURRENT name in the branch commit and let the later rebase-onto-main flip it. Read which name the branch baseline actually carries before resolving (`git show <branch-head>:<file> | grep -c '_sh_live'`) — do not assume branch and main agree.

## Two commits with the same parent and subject are SIBLINGS — base on the canonical one, and a test red on your base may be sibling drift

A rebase lane can cut the SAME union twice: two commits with an identical parent and an identical subject, differing only in a trivial tree delta (a couple of test lines). They look interchangeable and `git log` reads them as the same change, but **neither is an ancestor of the other** — `git merge-base --is-ancestor A B` is false in both directions. A branch based on the non-canonical sibling will NOT fold cleanly into the diff of the head the owner actually lands.

- Before choosing a prep base, prove ancestry instead of trusting the subject: `git merge-base --is-ancestor <candidate> <canonical-head> && echo ancestor || echo SIBLING`. If it is a SIBLING, rebase onto the canonical head (`git rebase --onto <canonical> <sibling-you-were-on> HEAD`) before pushing the reference branch.
- **A test red on your base can be sibling drift, not your change.** When 1–2 tests fail in a file you never touched, diff your base against the canonical base before blaming your own diff: `git diff <your-base> <canonical-base> --stat`. A non-empty delta there means the canonical base already carries a fix (e.g. a monkeypatch the failing tests need) that your sibling lacks — rebasing onto the canonical base makes them pass with no edit to your change. Report it as "base-sibling behavior, resolved by the correct base", never as a regression your change introduced.
- Same hazard for a hand-picked `git diff A..B` comparison: sibling trees differ, so a diff taken against the non-canonical sibling shows changes that are NOT yours and omits changes that ARE. Always diff against the base you will actually land on.

## A canonical union that is RE-CUT onto a new main tip supersedes your base — re-anchor, do not assume ancestry holds

A union head you already based a branch on is not permanent: when the owner orders a rebase, the lane re-cuts the SAME union onto the CURRENT live-main tip, producing a NEW head sha whose parent is the new tip. Your branch, anchored on the OLD union head (whose parent was an older tip), is now behind and will not fold into the diff of the head that actually lands. The subject line of old and new union heads is identical, so `git log` reads them as the same change — check the parent, never the subject:

```bash
git rev-parse <new-union>^        # must equal the live tip you are told main is at
git log --oneline -2 <new-union> # subject matches your old base; parent differs → re-cut
```

- Re-anchor with the three-arg form, passing your OLD base (the previous union head) as `<upstream>` so only your own commits replay: `git rebase --onto <new-union> <old-union-base> HEAD`. Then `git checkout -B <branch> HEAD` (the rebase can leave a detached HEAD) and confirm the new base: `git rev-parse HEAD^^ == git rev-parse <new-union>`.
- Re-cut unions can carry OTHER lanes' files the old base never had (a sibling PR merged into the union). Run the suite INCLUDING those carried files' tests, not only your own — a green on your files that skips the union's newly-added test modules has not proven "no collision with the union". Quote the per-file counts so the union-carried modules are visibly in the green.
- The `engine-build-pr-trigger` producer fires at the pushed PR-head sha. When the re-cut head has not been force-pushed to the PR branch yet, the producer has NOT re-fired — say "trigger at the new head not yet fired, PR head still <old sha>" and hold, rather than reporting the alignment as complete. Pre-anchoring your branch onto the re-cut head (so it is ready to fold) is the correct state to report while waiting.

## The deliverable is the LIVE PR branch — a scratch/prep branch is not the fix

A fix parked on a scratch branch (`prep/…`, a detached HEAD, a `lane-slug-shortsha` ref) is invisible to the PR, to `check-pr-base`/`check-pr-closing`, and to the `engine-build-pr-trigger` producer that only dispatches at the pushed branch head. Committing and verifying there and calling it "the task-relative change" is a no-op a lane-guard flags as "no mutation" even though work happened. Land the fix on the actual PR head branch: reset that worktree to the remote head, cherry-pick or re-apply the one commit, verify at that branch head — then hold for the lease-push only when a stop order forbids pushing. Park-refs are for a blocked push at an already-correct branch, never a substitute for landing the commit.

**A rebase, a branch re-point, or a `git checkout -B` is NOT a file-content mutation** — it changes no file, so it does not satisfy a completion guard that wants a changed file verified. Pair every branch move with the actual content edit run through its real gate: the mutation the guard accepts is "this file changed AND its test/gate passed at the new head", not "the branch moved onto a better base" (moving the base is the correctness fix; proving the file content is the mutation).

## A `git rebase --continue` that times out is an editor prompt, not a crash — retry non-interactively

A `rebase --continue` (or `cherry-pick --continue`) can hang its terminal call past the tool timeout on the same step that seemed to "kill the commit": git is waiting on an editor for the commit message. Nothing is corrupt — inspect `git status` / `.git/worktrees/<wt>/rebase-merge` (rebase state lives in the SHARED repo's worktree dir for a linked worktree, not the worktree's own `.git`, which is a file) and confirm the pick applied but the commit did not. Retry with the editor disabled: `GIT_EDITOR=true git rebase --continue`. Then confirm `git rev-parse HEAD` advanced past the base and the tree is clean before running the suite — never assume "the continue hung" means the rebase failed.

## Do NOT resolve a git conflict block with the fuzzy `patch` tool

A file still carrying `<<<<<<<`/`=======`/`>>>>>>>` markers is not a normal string-match target: the fuzzy patch matcher can land inside the conflict region and produce a second mangled block (`.UU` state, `IndentationError`) instead of a clean resolution. Resolve by rewriting the exact line range of the block (a small script over `read().splitlines()`: `lines[:start-1] + clean_lines + lines[end:]`), or `git checkout --ours/--theirs <file>` then re-apply the real change — then `git add` and `git cherry-pick --continue`. Always re-assert after: `grep -nE '<<<<<<<|=======|>>>>>>>' <file>` prints nothing and `python -m py_compile <file>` is clean.

**`git branch -f <branch>` refuses with `cannot force update the branch ... used by worktree` when the branch is checked out.** `git checkout --detach HEAD` (or `-q <other-ref>`) first, then `git branch -f`, then `git checkout <branch>` — otherwise the ref never moves.

**A `git rebase --onto <newbase> <oldbase> HEAD` run while a branch is checked out can finish with `Successfully rebased and updated detached HEAD` — and leave the branch ref pointing at the OLD tip.** Verify before pushing: `git branch --show-current` must print the branch, not be empty, and `git rev-parse <branch>` must equal `git rev-parse HEAD`. If it detached, `git branch -f <branch> <new-head> && git checkout <branch>` to move the ref, then push. Pushing a detached HEAD to the branch name is fine for the remote, but a subsequent local operation (or another lane reading the branch ref) then sees the stale sha.

**A rebase run in a worktree that does not own the branch leaves the result on a DETACHED HEAD, and `git push origin <branch>` then pushes the STALE local ref.** `git checkout -B <branch>` refuses (`branch is checked out at <other worktree>`), so the rebased commit never reaches the ref; a plain `git push origin <branch>` exits 0 while reverting the remote to the old sha. Push the commit you actually made — `git push --force-with-lease=<branch>:<old-sha> origin HEAD:<branch>` — and read `gh api repos/O/R/branches/<branch> --jq .commit.sha` back; the exit code does not tell you which sha arrived. Then confirm the branch tree still holds both sides of the change (`git show <sha>:<file>`), because a stale push looks exactly like a successful one.

**When the branch is checked out elsewhere and the push is not allowed yet, park the commit on a NEW ref — a detached HEAD commit is unreachable and `git gc` can take it.** `git branch -f` cannot move a branch another worktree owns, so name your own ref instead of colliding: `git update-ref refs/heads/<lane>-<slug>-<shortsha> <sha>`, then prove the commit is addressable (`git branch --contains <sha>`) and run the module's own tests at it. Record the ref name plus that test result in the PR/issue comment, so the later lease-push (`git push --force-with-lease=<branch>:<remote-sha> origin <sha>:refs/heads/<branch>`) is a named, verified step rather than a lost sha.

**A LOCAL park-ref is invisible to the canonical repo and to a lane-guard that reads `ls-remote` — publish it to `origin` as a NEW bare branch to make it a verifiable deliverable, and know that this does NOT trigger the engine-build producer.** When a stop order forbids pushing the PR head but the resolution must be exchangeable/verifiable from the canonical repo, push the parked commit under a fresh, clearly-labelled name that has **no PR**: `git push origin <sha>:refs/heads/<lane>-<slug>-verified`, then prove it with `git ls-remote origin refs/heads/<lane>-<slug>-verified` and confirm the never-kill PR head is untouched (`git ls-remote origin refs/heads/<pr-branch>` still the old sha). This is safe because `engine-build-pr-trigger.yml` keys on **pull_request** events — a bare branch with no PR fires nothing, so there is no dispatch and no storm; only a push that creates/updates a PR or is a PR head dispatches. A `git push origin <sha>:refs/heads/<newname>` therefore makes the work durable and adoptable (`git fetch origin <newname>`) without touching the PR head. Verify readability before reporting: a linked-worktree-only commit is unreadable from the primary checkout and reads as "no mutation" even though the work is real.

**Which remote to push to is the PR's head repo, not a fixed list.** Read `.head.repo.full_name` from the PR API; for a cross-repo PR that is the fork (`andyholst/llgenie`), so the force-push goes to `fork`, not `origin`. The same-named branch on the two remotes can hold DIFFERENT shas (`git ls-remote fork` vs `git ls-remote origin refs/heads/<branch>`) — the PR head is whichever the API names, and the other is a stale leftover that does not need a push. After pushing, verify `gh api .../pulls/<n> --jq .head.sha` equals the full 40-char sha you pushed. If `gh api` for check-runs returns empty right after a push, the runs have not re-materialized at the new head yet — query the runs API keyed by full `head_sha`, not the PR check-runs endpoint.

## Never tick an openspec box that claims a green run without a real green run

`make ci-openspec` fails on ANY unchecked `- [ ]`, so unticked boxes keep the gate red — but a box asserting "engine-build <engine>/<arch> push=false green (run id + head sha)" may only be ticked against a run that actually concluded green at the right head.

- A run that is `pending`/`in_progress` with ZERO materialized jobs, or that sits at an OLD pre-rebase head, is NOT proof. A proof dispatch at an old head is moot once the branch rebased; re-dispatch at the new head.
- Dispatch a narrow proof at the PR head: `gh workflow run <engine-build> -r <pr-branch> -f engine=<x> -f arch=<y> -f push=false`, then watch it keyed on the FULL 40-char sha. A narrow `push=false` proof shares the per-cell build group, so it slots in after other in-flight builds of that cell — pending-with-zero-jobs shortly after dispatch is normal queueing, not a dead run; check the fleet's concurrent cell before assuming a hang.
- Tick and repush only when the proof returns green. Report an in-flight proof as in-flight, never as green — a box ticked on a dead or pending run is fabricated evidence that reds the gate again later when someone checks.
