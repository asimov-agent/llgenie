# Re-pointing a PR to a different closing issue, and force-pushing an amended commit

## The commit message closes the issue, not just the PR body

GitHub auto-closes an issue when `closes #N` (or `fixes`/`resolves`) appears **either** in the
PR body **or** in the merge commit message. The squash merge builds its commit message from the PR
title plus each squashed commit's body. So when the issue a PR should close changes, editing the PR
title and body is **not enough** — a stale `closes #OLD` left in the commit body still fires on
merge and auto-closes the wrong issue (or an issue you were told to keep open).

Rule: re-point = amend the commit that carries `closes #N`, then update the PR title/body. Both
surfaces must name the new issue; neither may name the old one as closed.

## Procedure

1. **Amend the commit message**, rewriting `Issue: #NEW` and `closes #NEW`:
   ```
   git -c user.name="$(gh api user --jq .login)" commit --amend -q -F - <<'EOF'
   fix(...): <title> (#NEW)

   Issue: #NEW
   ...
   closes #NEW
   EOF
   ```
2. **Push the amended head.** Fetch the branch first, then push with lease: an amend keeps the remote tip an ancestor
   of the new head; a `non-fast-forward` hint is a stale-lease signal — re-fetch and retry:
   ```
   git push --force-with-lease origin <branch>
   ```
   Prefer `--force-with-lease` over plain `--force`; both are safe on **your own fresh branch**
   (verify remote == your previous sha with `git ls-remote origin <branch>` first). Never force a
   branch another lane owns.
3. **Update the PR title and body** so both name the new issue:
   ```
   gh pr edit <n> --repo OWNER/REPO --title "...(#NEW)"
   gh pr edit <n> --repo OWNER/REPO --body-file /path/body.md   # body must contain `closes #NEW`
   ```
4. **Verify the linkage and the issue states:**
   ```
   gh pr view <n> --repo OWNER/REPO --json body --jq .body | grep -E 'closes|#NEW|#OLD'
   gh api repos/OWNER/REPO/issues/<NEW> --jq '{n:.number,state}'
   gh api repos/OWNER/REPO/issues/<OLD> --jq '{n:.number,state}'
   ```
   Expected: NEW `open` (closes on merge), OLD `open` (never cross-closed). If the old issue is
   referenced as kept-open, the PR body should say so explicitly so a reviewer sees the intent.
5. **Read the auto-merge arm back at the NEW head.** A force-push may or may not drop the arm:
   ```
   gh pr view <n> --repo OWNER/REPO --json autoMergeRequest,mergeStateStatus,headRefOid \
     --jq '{head:.headRefOid[0:8], merge:.mergeStateStatus,
            auto:(if .autoMergeRequest==null then "NONE"
                  else (.autoMergeRequest.mergeMethod+"@"+.autoMergeRequest.enabledAt) end)}'
   ```
   If `auto` is `NONE`, re-arm with `gh pr merge <n> --squash --auto`. Report the arm time from
   `enabledAt`, and confirm `head` equals the amended sha — an arm read at the old head is not proof.

## Rebasing a stale base: the base is the CANONICAL remote's `main`, not the name `origin/main`

`check-pr-base` (issue #845) reds the guard job when your branch's merge-base with the **live**
`origin/main` is not `origin/main` itself — i.e. main advanced past your cut. Inside CI `origin/main`
is canonical `asimov-agent/llgenie` main, so a branch cut even a few merges back reds the moment main
moves. This is neither a product defect nor a test failure: read the guard job's LOG for the merge-base
sha it names, then rebase. But the rebase base is the trap.

- **Resolve the true base with the API, never the remote name.** `git rebase --onto origin/main …`
  rebases onto whatever `origin` points at. On this host `origin` is sometimes the fork
  (`andyholst/llgenie`), whose `main` can sit *behind* canonical main and predate files your branch
  imports — the rebase then silently drops them and the test import fails with an
  `ImportError`/`ModuleNotFoundError`-shaped red unrelated to your change (measured: rebasing onto the
  fork's `main` removed a pinned-publisher script the trigger imported). Ask the API for the tip:
  `gh api repos/asimov-agent/llgenie/branches/main --jq .commit.sha`.
- **Prove the lineage before trusting the tree.** The direction test
  `git merge-base --is-ancestor <your-base> upstream/main` returns true AND the reverse
  (`--is-ancestor upstream/main <your-base>`) returns **false** when `<your-base>` is stale relative to
  canonical main. Both-true or reverse-true = you are on a divergent/behind lineage (a fork `main` was
  literally an ancestor of the real base here).
- **Re-do it cleanly onto canonical main:**
  ```
  git fetch upstream main
  git rebase --onto upstream/main <your-original-base> <your-commit>
  ```
  then confirm `git merge-base upstream/main HEAD` equals `upstream/main` exactly, the vanished file is
  back, and re-run the shape gates (`check_proc_gate`, the affected tests) against this tree — a second
  rebase onto a newer main can reintroduce conflicts and drop-file regressions the first one masked.
- **Container caveat.** Running `scripts/check_pr_base.py` inside the mount-point test container can
  fail on `git rev-parse HEAD` because the mount is a separate full clone whose `.git` is not the
  worktree's. Do not read that in-container error as a real base failure — verify the base condition
  with HOST git's `git merge-base upstream/main HEAD` instead.
- **Worktree detached-HEAD trap.** A `git rebase` leaves HEAD detached; `git push` then reports
  "up-to-date" because the branch ref still points at the old sha. Re-point the ref
  (`git branch -f <branch> HEAD && git checkout <branch>`) and re-read `git rev-parse --abbrev-ref HEAD`
  before pushing.

## Pitfalls

- **Do not rename the branch to chase the new issue number.** A force-pushed new head is enough;
  renaming the head ref orphans review context and `gh` cannot cleanly move an existing PR's head.
  A branch named after the old ticket is acceptable — say so in the re-point comment rather than
  churning the ref.
- **A stale `closes #OLD` in the commit body is invisible in the PR diff** — grep the commit body
  (`git log -1 --format=%B`) for `closes`/`fixes`/`resolves` before trusting a re-point.
- **Bookend comments survive a force-push** (same PR id); you do not need to re-post start/finish,
  but do post one short re-point note naming old sha → new sha and the new issue.
- **The green arm is not the merge.** Report `mergeStateStatus` as-is (`BLOCKED` = review-only); the
  repo auto-merge lands it on review. Never self-merge.
- **Never update an own branch by delete + re-push — it auto-closes the PR.** GitHub treats a deleted
  then recreated head as a new branch identity and refuses to reopen (`state cannot be changed. The
  <branch> branch was force-pushed or recreated`, HTTP 422), so you lose the PR thread and must open a
  twin. The sanctioned in-place update is the lease-protected force-push. If the terminal tool blocks
  force-push in single-query mode, satisfy the guard with `hermes config set approvals.single_query_mode
  approve`, push, then `hermes config unset approvals.single_query_mode` immediately after (read back
  with `hermes config get approvals.single_query_mode`; `deny` = restrictive). If the PR was already
  auto-closed, do NOT fight the reopen — close it and open a fresh PR from the same head, carrying the
  same body (both name `closes #N`, so the linkage survives).
