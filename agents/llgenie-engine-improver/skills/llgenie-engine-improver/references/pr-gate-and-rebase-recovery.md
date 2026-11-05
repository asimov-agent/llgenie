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

## The deliverable is the LIVE PR branch — a scratch/prep branch is not the fix

A fix parked on a scratch branch (`prep/…`, a detached HEAD, a `lane-slug-shortsha` ref) is invisible to the PR, to `check-pr-base`/`check-pr-closing`, and to the `engine-build-pr-trigger` producer that only dispatches at the pushed branch head. Committing and verifying there and calling it "the task-relative change" is a no-op a lane-guard flags as "no mutation" even though work happened. Land the fix on the actual PR head branch: reset that worktree to the remote head, cherry-pick or re-apply the one commit, verify at that branch head — then hold for the lease-push only when a stop order forbids pushing. Park-refs are for a blocked push at an already-correct branch, never a substitute for landing the commit.

## Do NOT resolve a git conflict block with the fuzzy `patch` tool

A file still carrying `<<<<<<<`/`=======`/`>>>>>>>` markers is not a normal string-match target: the fuzzy patch matcher can land inside the conflict region and produce a second mangled block (`.UU` state, `IndentationError`) instead of a clean resolution. Resolve by rewriting the exact line range of the block (a small script over `read().splitlines()`: `lines[:start-1] + clean_lines + lines[end:]`), or `git checkout --ours/--theirs <file>` then re-apply the real change — then `git add` and `git cherry-pick --continue`. Always re-assert after: `grep -nE '<<<<<<<|=======|>>>>>>>' <file>` prints nothing and `python -m py_compile <file>` is clean.

**`git branch -f <branch>` refuses with `cannot force update the branch ... used by worktree` when the branch is checked out.** `git checkout --detach HEAD` (or `-q <other-ref>`) first, then `git branch -f`, then `git checkout <branch>` — otherwise the ref never moves.

**A `git rebase --onto <newbase> <oldbase> HEAD` run while a branch is checked out can finish with `Successfully rebased and updated detached HEAD` — and leave the branch ref pointing at the OLD tip.** Verify before pushing: `git branch --show-current` must print the branch, not be empty, and `git rev-parse <branch>` must equal `git rev-parse HEAD`. If it detached, `git branch -f <branch> <new-head> && git checkout <branch>` to move the ref, then push. Pushing a detached HEAD to the branch name is fine for the remote, but a subsequent local operation (or another lane reading the branch ref) then sees the stale sha.

**A rebase run in a worktree that does not own the branch leaves the result on a DETACHED HEAD, and `git push origin <branch>` then pushes the STALE local ref.** `git checkout -B <branch>` refuses (`branch is checked out at <other worktree>`), so the rebased commit never reaches the ref; a plain `git push origin <branch>` exits 0 while reverting the remote to the old sha. Push the commit you actually made — `git push --force-with-lease=<branch>:<old-sha> origin HEAD:<branch>` — and read `gh api repos/O/R/branches/<branch> --jq .commit.sha` back; the exit code does not tell you which sha arrived. Then confirm the branch tree still holds both sides of the change (`git show <sha>:<file>`), because a stale push looks exactly like a successful one.

**When the branch is checked out elsewhere and the push is not allowed yet, park the commit on a NEW ref — a detached HEAD commit is unreachable and `git gc` can take it.** `git branch -f` cannot move a branch another worktree owns, so name your own ref instead of colliding: `git update-ref refs/heads/<lane>-<slug>-<shortsha> <sha>`, then prove the commit is addressable (`git branch --contains <sha>`) and run the module's own tests at it. Record the ref name plus that test result in the PR/issue comment, so the later lease-push (`git push --force-with-lease=<branch>:<remote-sha> origin <sha>:refs/heads/<branch>`) is a named, verified step rather than a lost sha.

**Which remote to push to is the PR's head repo, not a fixed list.** Read `.head.repo.full_name` from the PR API; for a cross-repo PR that is the fork (`andyholst/llgenie`), so the force-push goes to `fork`, not `origin`. The same-named branch on the two remotes can hold DIFFERENT shas (`git ls-remote fork` vs `git ls-remote origin refs/heads/<branch>`) — the PR head is whichever the API names, and the other is a stale leftover that does not need a push. After pushing, verify `gh api .../pulls/<n> --jq .head.sha` equals the full 40-char sha you pushed. If `gh api` for check-runs returns empty right after a push, the runs have not re-materialized at the new head yet — query the runs API keyed by full `head_sha`, not the PR check-runs endpoint.

## Never tick an openspec box that claims a green run without a real green run

`make ci-openspec` fails on ANY unchecked `- [ ]`, so unticked boxes keep the gate red — but a box asserting "engine-build <engine>/<arch> push=false green (run id + head sha)" may only be ticked against a run that actually concluded green at the right head.

- A run that is `pending`/`in_progress` with ZERO materialized jobs, or that sits at an OLD pre-rebase head, is NOT proof. A proof dispatch at an old head is moot once the branch rebased; re-dispatch at the new head.
- Dispatch a narrow proof at the PR head: `gh workflow run <engine-build> -r <pr-branch> -f engine=<x> -f arch=<y> -f push=false`, then watch it keyed on the FULL 40-char sha. A narrow `push=false` proof shares the per-cell build group, so it slots in after other in-flight builds of that cell — pending-with-zero-jobs shortly after dispatch is normal queueing, not a dead run; check the fleet's concurrent cell before assuming a hang.
- Tick and repush only when the proof returns green. Report an in-flight proof as in-flight, never as green — a box ticked on a dead or pending run is fabricated evidence that reds the gate again later when someone checks.
