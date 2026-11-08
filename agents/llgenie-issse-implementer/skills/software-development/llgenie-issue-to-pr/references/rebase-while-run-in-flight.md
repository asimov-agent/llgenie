# Rebasing a PR branch while a verification run is in flight

Use when the owner directs a rebase of an open PR branch onto latest main while a
`workflow_dispatch`/verdict run is still running at the current head. The default
rule is "rebase only when `CONFLICTING`, never on every main move" (#1015), but an
explicit owner directive overrides it — verify the trigger first with
`gh pr view <n> --json mergeable` and record which applied (owner-directed vs
conflict-driven) in the report.

## Procedure (stage locally, do NOT push until licensed)

1. **Fetch main with an explicit refspec**: `git fetch origin '+refs/heads/main:refs/remotes/origin/main'`.
   Never trust the stale local `refs/heads/origin/main` short-ref.
2. **Confirm the run is genuinely in flight**: `gh run view <run-id> --json status`
   plus the specific job id. A force-push that rewrites the head mid-run can
   invalidate the verdict or forfeit an arm — the caution is real, not ceremonial.
3. **Stash uncommitted working-tree edits that must NOT ride the rebase** (e.g. a
   premise/comment fix held for a later decision): `git stash push -m "..." <path>`.
   Keep them out of the rebased commits.
4. **Rebase with `--onto` so you control the replay base**:
   `git rebase --onto origin/main <old-base-sha>`. The old base is the PR's
   `base.sha`, not a guessed merge-base.
5. **Verify byte-identity of the substantive files against the on-wire head**:
   `git diff <old-head> HEAD --stat -- <substantive files>` must be EMPTY. Only
   main's own newly merged files should appear in the overall stat diff.
6. **Stage only — do NOT push.** Confirm the origin branch still points at the old
   head: `git rev-parse --short origin/<branch>`.
7. **Report planned base/head shas and the push-license condition.** The push is
   licensed by EITHER the in-flight run concluding OR explicit owner go. After the
   run concludes: force-push `--force-with-lease --force-if-includes`, then **NO
   re-dispatch** (two-vehicle rule — a second dispatch races the same files).
8. **Restore stashed working-tree edits only when their own decision lands**
   (post-run), never as part of this rebase.

## Pitfalls

- A rebase worktree often ends on a **detached HEAD** (it tracks a branch checked out
  elsewhere). That is normal after `--onto`; the shas are still correct.
- Don't let a stash get lost: re-list `git stash list` before reporting and confirm
  the held fix is still `stash@{0}` (or wherever it landed).
- The overall `git diff old-head HEAD --stat` will show main's newly merged files —
  that is expected and NOT a byte-identity failure. Byte-identity is measured ONLY
  over the PR's own substantive files.
- Distinguish WHICH run the caution protects. A `workflow_dispatch`/verdict cell
  pinned at an OLDER cap sha is NOT the current PR head: it runs on its own
  checkout, so moving the PR head to new (rebased) shas does not cancel it. An
  in-progress cell at a sha different from the PR head therefore does NOT block an
  owner-licensed force-push — the caution applies when the in-flight run IS at the
  head you are about to rewrite. Confirm before deciding: compare
  `gh run view <id> --json headSha,status` against `gh pr view <n> --json headRefOid`.
- The LOCAL branch ref can point at an orphaned line that never reached origin (an
  abandoned divergent commit) while `origin/<branch>` is the real PR head.
  `--force-with-lease` guards the ORIGIN value, not your local ref, so verify the
  real head right before the push with
  `git fetch origin '+refs/heads/<branch>:refs/remotes/origin/<branch>'` (or
  `git ls-remote origin <branch>`) — never a bare `git rev-parse <branch>`.
