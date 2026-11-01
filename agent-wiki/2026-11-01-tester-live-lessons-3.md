# Tester lane live→tree sync, cycle-3 post-#1260 — three verification lessons

The #1260 sync (the fleet SOUL/skill "RELOAD" round, live→tree) merged at `7ac0bc02` (2026-11-01
00:33:57Z). Its verify work generated three real lessons that live only in the live profile's
SKILL.md — this cycle folds them byte-for-byte into the tree.

## 1. A poller must re-check the branch tip every iteration

A loop that only watches check state reports a superseded head as a concluded verdict: a rebase or
force-push during the poll moves the branch and cancels the watched run, but the loop keeps reading
the old run's `completed` result and wakes up describing a tree the PR no longer carries. Guard the
head inside the loop — compare `git ls-remote origin <branch>` at the top of each cycle, before
reading check state — and when a completion notification arrives, check its sha against the current
head before acting on it. (Measured on the #1260 second rebase: two stale `ALL_CONCLUDED@<oldsha>`
wake-ups.)

## 2. `main` moving under a head whose CI is in flight is NOT a rebase trigger

The unit matrix takes tens of minutes and a busy fleet merges every few minutes, so any rebase "onto
the newest main" is stale again before its run concludes, and each rewrite cancels the matrix that
was about to produce the verdict. A head on an older `main` still merges, and its green is a valid
verdict FOR THAT HEAD — quote both shas (§5) and let the merge queue rebase-if-needed. Re-base only
when the head actually goes `CONFLICTING` (`git merge-tree --write-tree <fresh-main> <head>` non-zero)
or when a fix landed on `main` that the head must pick up — and say which of the two drove the
rewrite. (The #1015 class: "rebase only when actually CONFLICTING". Chasing a moving main is the
recurring-drift tracker's exact pathology. The planner confirmed: since GitHub computes mergeability
vs the live default branch, a stated older base with mergeable=true needs no re-rebase.)

## 3. Put `.state`/`.mergedAt` in the arm read-back every time

`auto_merge.enabled_at: null` with `enabled_by` populated is the identical read for two opposite
situations — the arm did not register, and the PR was already CLOSED/MERGED before the arm could
register. Only `.state`/`.mergedAt` tells them apart. Skipping it turns a finished PR into an endless
"why won't it arm" loop: re-issuing `gh pr merge --auto` and re-reading `auto_merge.*` in fresh jq
variants returns the same null forever, because the field being stared at can no longer change. When
the read-back does not flip, the FIRST next move is a full `gh api repos/<o>/<r>/pulls/<n>` object
dump — the answer is usually a field you did not filter for. (The #964 sharpen: on #1260 my arm
attempts raced the owner's own merge; on a closed/merged PR `mergeable=UNKNOWN` is not even a
question.)

## Also carried

- The completion-integrity false-positive explanation sharpened to THREE hashes: `git cat-file blob
  <base>:<path>` (the tree the detector scans), `git cat-file blob <head>:<path>` and `sha256sum <
  "$LIVE/<path>"` (the branch==live proof). `head==live` proves the change; `base!=head` proves the
  demand is only satisfiable by a merge you are gated from.

Clears the fresh llgenie-tester rows of the #1079 drift tracker (generic per-lane vehicle). Does NOT
close #961 / #1060 / #1079.
