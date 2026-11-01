# tester lane live→tree fold, round 7 (2026-11-01)

Versioning the tester lane's live→tree drift at `4cb8b345` (#1281's merge). Live accreted two
lessons this round, both proven in real time by the fold that just landed. Pure accretion; byte-copied
live→tree, not-mid-write proven (double-read), re-hashed.

## Lesson 1 — a branch-gone is a STATE read, not "head moved"

An empty `ls-remote` for the watched branch is its own outcome: after the owner merges and
`delete_branch_on_merge` reclaims the ref, the empty result must branch to
`gh pr view <n> --json state,mergedAt,mergeCommit` — NEVER be folded into the `HEAD_MOVED` case. The
`[ -z "$h" ]` guard comparing `"${h:0:8}"` against a watched sha makes the empty ref satisfy the
inequality and report `HEAD_MOVED to <blank>`, which sends you hunting for a new CI cycle on a branch
that no longer exists. #1281's watcher hit exactly this; the fix (state-read first) is what verified
the merge cleanly.

## Lesson 2 — a fold's proof is at the MERGE COMMIT against CURRENT `origin/main`

A squash merge is a new tree whose sha you never authored, so matching live at your PR **head** only
proves the head was right, and a drift table computed against your PR's **base** reports files drifted
that have since landed. After the merge: fetch, then per folded path compare
`git cat-file blob <merge-commit>:<path> | sha256sum` against `sha256sum < "$LIVE/<path>"` AND confirm
`git merge-base --is-ancestor <merge-commit> origin/main`. That pair = "fold held and it is on the
default branch." When live has already moved past the merge commit, report both facts in one line
(`held at <merge>; drifted since at <live>`) — the next delta is the expected next round, never
evidence of failure. Enumerate drift against `origin/main`'s blob per file (`git ls-files
agents/<profile>`), so a file that landed last round can't be miscounted as open drift.

## Proof at the committed head

`SKILL.md` and `agent-profile-versioning.md` both byte-identical to live; enumerate vs
`origin/main` = `4cb8b345`; SOUL + all other reference files unchanged byte-for-byte.
