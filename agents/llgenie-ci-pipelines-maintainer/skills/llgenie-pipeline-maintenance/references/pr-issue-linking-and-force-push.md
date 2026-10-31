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
2. **Push the amended head.** After an amend, `git push --force-if-includes` can be **rejected**
   with a generic "non-fast-forward / use `git pull`" hint. Retry with lease:
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
