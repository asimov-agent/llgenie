# Reconciling a lane that cites a different head

Two directions of the same problem: another lane's quoted sha disagrees with what the
branch actually is. The measurement recipe is identical; only the reply differs.

Measure from independent sources in one turn — never argue from a DM log, never trust your
own worktree HEAD as truth (it is the sha you last BUILT locally, often based on older main):

```bash
gh api repos/<owner>/<repo>/git/refs/heads/<branch> --jq .object.sha
git ls-remote <remote> refs/heads/<branch>
gh pr view <n> --json headRefOid,mergeable,mergeStateStatus
git rev-parse HEAD          # least trustworthy — local build, may be stale
```

If branch ref + PR `headRefOid` + `git ls-remote` agree with each other but disagree with a
lane's quote, that lane is reading stale board state. If they disagree with *each other*, the
branch was re-pushed under you — origin / `headRefOid` wins, your worktree is stale. Inspect
the CURRENT head, not the one you remember.

## Direction A — a lane insists YOUR pushed head is older than it is

(e.g. "you keep quoting 48009b11", "branch still reads <old>", "head has not changed").

1. Say so ONCE, quoting all the measured shas and the gate result at the true head.
2. When the lane cites a SPECIFIC red run id / job id as proof the red is live, resolve that
   run's own `head_sha` and show it is the superseded head — that is the crispest rebuttal:
   ```bash
   gh api repos/<o>/<r>/actions/runs/<run_id> --jq '{head_sha:.head_sha[:12],conclusion}'
   gh api "repos/<o>/<r>/actions/runs/<run_id>/jobs?per_page=100" \
     --jq '.jobs[]|select(.name=="linux / unit")|{status,conclusion}'
   ```
   A failure whose `head_sha` is the OLD head is superseded, not a live red. Point at the
   fresh run at your true head and its per-leg verdicts (which green except any still PENDING).
3. Point at your existing per-head evidence comment (one message per head).
4. HOLD. Do not manufacture a "new push" to satisfy a verdict measured against a stale
   mirror — the acceptance gate at the true head is the contract. A lane repeating the same
   stale claim three times is loop-escape territory: hold, do not answer a fourth time.

## Direction B — a peer lane asks YOU (branch owner, rule #994) for a rebase all-clear

The peer quotes the head it read when dispatched; that sha is stale the moment a prior window
rebuilt or re-pushed the branch, so its "CONFLICTING" / "union needed" premise may be false.
Decide on the LIVE head, not the quote:

1. Fetch fresh main: `git fetch origin +refs/heads/main:refs/remotes/origin/main`
   (explicit refspec — a bare fetch leaves a stale `refs/remotes/origin/main`).
2. `git merge-tree origin/main <live-head>` — zero `CONFLICT` lines = MERGEABLE, no rebase owed
   (issue #1015). A MERGEABLE-but-behind branch is not broken.
3. `git diff <live-head>^ <live-head>` — confirm the live head ALREADY carries the content the
   peer believed was missing (the "union" they propose is often already in the rebuilt head).

The reply: grant all-clear for OWNERSHIP (you are not mid-edit, worktree clean) but say **do not
rebase**, quoting the live sha and the merge-tree result, and ask the peer to re-measure at that
sha before touching anything. Do not rebase a MERGEABLE branch to satisfy a dispatch; report the
stale premise to the dispatcher (planner) too, naming the live head.

## Direction C — YOUR branch is force-re-stacked by a peer rebase fleet

On a bump/sweep fleet, another lane may force-rebase your branch onto newer `main` while you
work, so the head moves under you several times in one session (e.g. `32da7665` → `2aa4a4ac` →
`e0645162`). Your commits reappear with identical messages but as NEW shas that are NOT
descendants of the sha you pushed.

- This is not damage to fight — treat the newest head as truth and re-verify your fix CONTENT
  survived it, because a rebase can silently drop or conflict away your row:
  ```bash
  git fetch origin +refs/heads/main:refs/remotes/origin/main
  gh pr view <n> --json headRefOid            # the live head
  gh api "repos/<o>/<r>/contents/<path>?ref=<live-head>" --jq .content | base64 -d  # value intact?
  git cat-file -p <live-head>                 # parent chain — is it stacked on a sibling now?
  ```
- Confirm the gate test at the newest head is the one that matters; a prior run at a superseded
  sha is irrelevant.
- Never force-push your old chain back over the fleet's re-stack — you would re-invalidate the
  sibling it stacked onto and rewrite shas a peer is working from. Measure, verify content, hold.

## Direction D — a lane re-dispatches an issue that is ALREADY MERGED as "still unclaimed"

The dispatcher keeps repeating "#<n> is still unclaimed, claim it off main <stale-sha>" while the
issue's squash is already the head of main. The receptionist/planner board is a summarised view and
can lag several merges behind the ref; the live API outranks it every time.

Measure the two facts that end the argument, in one turn:

```bash
gh api repos/<o>/<r>/git/ref/heads/main --jq .object.sha          # the TRUE main tip
gh api repos/<o>/<r>/issues/<n> --jq '{state,reason:.state_reason,closed_at}'
gh api repos/<o>/<r>/pulls/<pr> --jq '{state,merged,merged_at,merged_by:.merged_by.login,merge:.merge_commit_sha}'
git merge-base --is-ancestor <dispatcher-cited-sha> origin/main && echo yes   # proves it is stale/ancestor
```

If the issue is `state=closed reason=completed` AND its PR shows `merged:true` with
`merge_commit_sha` == the live main tip, the "dispatch" is a duplicate of LANDED work (rule #824).
Refusing it is not a lane-rule violation — it is the one-vehicle rule. A missing `bot-claim:`
comment on a MERGED, COMPLETED issue is a non-event; the delivery already happened.

Reply shape: accept any genuinely-correct parts of the board read, then state ONCE with the
measured sha that the issue is the merge at the head of main, name the concrete duplicate ground,
and stop. Do not re-claim, do not cut a worktree off the stale sha, and do not re-measure a fifth
time when the lane repeats — the API verdict is invariant; a loop of re-verification is just
churn. (Do not attribute shas the lane never cited to it; separate the stale-board dispute from
the other corrections, which may be true.)

## Direction E — the dispatched head is an ANCESTOR of the live branch tip

The dispatcher pins a head sha for the PR you are told to open, but that sha is not the
branch tip: `git merge-base --is-ancestor <dispatched-sha> <live-tip>` exits 0 and
`git log --oneline <dispatched-sha>..<live-tip>` shows commits the dispatch never mentioned.
The branch advanced past the dispatch — frequently because another lane kept appending.
Opening blind in either direction is wrong:

- Open at the LIVE TIP and you ship FILES beyond the dispatched scope, and those extra
  change-notes may assert claims that are now FALSE (a note saying "the tracked fix never
  landed" when its PR merged hours ago). The stale claim lands in the tree under your PR.
- Open at the DISPATCHED ancestor sha and you must force-rewrite a branch another lane owns.

Measure, then ask the OWNING lane which head to open, naming both shas, the extra file paths,
and any stale claim you found:

```bash
git log --oneline <dispatched-sha>..<live-tip>        # the commits the dispatch omitted
git diff --name-status <dispatched-sha> <live-tip>     # the extra files (scope creep)
git diff --stat origin/main...<dispatched-sha>        # confirm the dispatched sha is the clean scope
```

Do NOT silently pick and do NOT force-push their branch. A dispatch that pins an ANCESTOR sha
is itself a stale-board signal: quote `git log -1 <sha>` plus the commit count to the tip, and
say plainly which head ships which scope. The owner decides; you measure and hold.

## Before opening ANY PR — base check (a pushed-but-no-PR branch is NOT churn-protected)

`check-pr-base` reds unless the branch's merge-base with current main IS current main:

```bash
git fetch origin +refs/heads/main:refs/remotes/origin/main
git merge-base origin/main <tip>          # must equal the main tip, else the base is stale
git rev-parse origin/main                  # the value it must equal
```

A dispatch's stated base is a snapshot; if `git merge-base origin/main <tip>` is an ANCESTOR of
`origin/main` (the branch was cut from an older main), the first PR will red `check-pr-base`.
The #1015 no-chase rule protects an ARMED / under-review PR from churn — it does NOT protect a
branch you have not opened yet. Rebase such a branch onto current main BEFORE the first push,
and regenerate the AGENTS:/BASE: line to the new main sha.

## Pitfalls

- `gh pr view --json` with a jq expression that concatenates a string field fails
  (`cannot add: string and object`) — query fields individually or use `gh api`.
- Do not hand-write a live profile file to "sync" a tree-only lint blank; that is the owning
  lane's `make sync-agent-profile` job and not a gate class.
