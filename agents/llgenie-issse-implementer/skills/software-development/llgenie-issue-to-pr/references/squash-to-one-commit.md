# Owner-directed squash to ONE commit + force-push (safe over a running cell)

When the owner asks to collapse a PR's commit stack into one commit, rewrite the message, force-push, and update the PR/issue bodies.

## Preconditions — ground the remote and the lease before touching anything
- Confirm which remote maps to the PR repo, not a fork: `git remote -v`, then `git ls-remote <remote> refs/heads/<branch>`. A fork remote (`andyholst`) is NOT the PR repo; the PR repo remote (`origin` -> `asimov-agent/llgenie`) is the one to push to.
- Record the live wire head as the lease target (`git ls-remote origin refs/heads/<branch>`).
- A verdict/CI cell already running at a pinned sha on an **independent concurrency group** is NOT cancelled by rewriting the branch — confirm the cell's group/head first, and a rewrite is then safe to run while it is still in flight. A cell whose group is the branch's own (`cancel-in-progress`) WOULD be cancelled: in that case do not rewrite under it.

### A `cancelled` conclusion is a claim, not (necessarily) your doing
An independent-group cell pinned at a sha ≠ your head runs its own checkout, so your force-push cannot cancel it. If such a cell nonetheless reads `cancelled` near your push, do NOT attribute it to the rewrite and do NOT report it as a time-wall — measure the cause before saying a word:
- Compare the cancel's own log timestamp against the push. `gh run view <id> --log | grep 'The operation was canceled'` gives the step's cancel time; `gh api repos/<o>/<r>/pulls/<n> --jq .pushed_at` gives the push time. A cancel stamped BEFORE `pushed_at` was not caused by the push.
- Read `gh api repos/<o>/<r>/actions/runs/<id> --jq '{event,actor:.actor.login,triggering_actor:.triggering_actor.login,head_sha,conclusion}'`. A `workflow_dispatch` with an owner `actor`/`triggering_actor` and a run far under the wall is a manual/owner cancel — an earlier event, not your rewrite.
- `gh run view <id> --log-failed` prints NOTHING for a `cancelled` run (a cancel is not a failure). Use `--log` and grep the build step's last lines; `--log-failed` on a cancel is an empty read, not "no error".

## Procedure
1. Confirm the stack sits atop the intended base and the range is exactly your commits:
   `git merge-base <base> <head>`; `git log --oneline <base>..<head>`.
2. Record the pre-squash tree — the identity you must preserve: `git rev-parse <head>^{tree}`.
3. Soft-reset to base and make ONE commit: `git reset --soft <base>`, then `git commit` with a multi-point message that ENDS with the same `closes #N` lines the PR body carries. Preserve the author identity used through the stack (`--author`, or `GIT_AUTHOR_NAME/EMAIL`).
4. Prove the tree is byte-identical: `git rev-parse HEAD^{tree}` must equal step 2. If it differs, you changed content — stop and inspect the diff.
5. Re-run the gates at the new head: `make check-docs check-workflows check-wiring lint`, `python3 scripts/check_pr_closing.py` (expect `squash closes: {…}` == body closes), and `python3 scripts/check_pr_acceptance.py check --body-file <live-body.md>` (the designed self-red, if any, shows here unchanged).
6. Force-push with lease: `git push --force-with-lease=<branch>:<oldhead> origin <branch>`. The explicit-lease form frequently rejects with `! [rejected] ... (stale info)` / "tip of your current branch is behind" EVEN when your expected sha is exactly the live wire head — rebuilding the remote-tracking ref first (`git update-ref refs/remotes/origin/<branch> <sha>`) does NOT make it accept. After a fresh `git fetch origin`, use the plain form instead: `git push --force-with-lease origin HEAD:refs/heads/<branch>`. Confirm the wire head: `git ls-remote origin refs/heads/<branch>` == the new sha. Also re-read `gh pr view <n> --json headRefOid` after pushing — the merge queue can re-squash/reshape the branch head (a new sha authored by the bot lane) under you between your last read and your push, so the head you report must be the wire head you just confirmed, not an earlier local sha.
7. Update the PR body: re-run `make bot-preflight` and copy its LITERAL `AGENTS:`/`BASE:` lines (never hand-write them, #792); set `Head:` to the new short sha; keep every `closes #N` line intact. Patch via `gh pr edit`/`gh api -X PATCH`, then read back `head.sha`, `commits=1`, `mergeable`.
8. Update the linked issue bodies with a squash-status note, but NEVER tick an acceptance box, NEVER strip a `closes` line, NEVER add a `## Not covered` deflection (#1792). The acceptance `- [ ]` parse must stay untouched — verify the unticked counts are unchanged after the edit.

## Post-rewrite reconciliation — a peer's head figure is now stale
- After any force-push/rewrite, a planner or peer lane quoting the OLD head is measuring a sha that no longer exists. Re-assert the wire head (`git ls-remote`) and send the corrected sha to that lane with a one-line "your figure is the pre-rewrite head" note; otherwise it confirms gates against a dead head.
- **A `cancelled` (or otherwise concluded) cell no longer witnesses anything.** Once a cell that was supposed to prove acceptance criteria concludes `cancelled`, the criteria it carried are UNWITNESSED — say so, never let a peer keep treating it as the live carrier. Re-derive which run now proves them: your own push's `pull_request synchronize` fires a fresh `pr-trigger` (`gh run list --json databaseId,event,status,headSha` — look for `event=pull_request` at your new head, `status=pending`), which will dispatch the `push=true` producer at the new head. Report that trigger as the proof path and **do NOT manually re-dispatch** (#824) — the trigger does it.
- Verify the gates on the NEW head, not the old one: `check-pr-closing` must log `[check-pr-closing] OK` in the fresh run, and the designed `check-pr-acceptance` self-red persists unchanged (it is not a squash regression — do not go looking for a code defect).
