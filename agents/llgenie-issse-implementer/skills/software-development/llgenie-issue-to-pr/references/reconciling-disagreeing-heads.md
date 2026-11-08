# Reconciling a lane that cites a different head

Two directions of the same problem: another lane's quoted sha disagrees with what the
branch actually is. The measurement recipe is identical; only the reply differs.

Measure from independent sources in one turn — never argue from a DM log, never trust your
own worktree HEAD as truth (it is the sha you last BUILT locally, often based on older main),
and never trust a peer's quoted sha even when the peer says it "just re-verified at <time>" —
`main` advances under every lane, so a correction timestamped minutes ago already cites a
superseded tip. Two peers can each quote a DIFFERENT stale base and neither is current; the live
API read NOW wins. Measure it in the same turn you correct a corrector:

```bash
gh api repos/<o>/<r>/commits/main --jq '.sha + " " + (.commit.message|split("\n")[0])'
gh pr view <n> --json headRefOid,baseRefOid,mergeable,mergeStateStatus
```

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

## Direction F — a LIVE "wait for the other lane's head" dispatch (hold, prep, acknowledge)

Distinct from Direction A–E: there the wait gate is stale/already resolved. Here the wait is
GENUINE and ACTIVE — the dispatcher re-issued a rebase/owner dispatch this turn and tells you
"WAIT for the landed head first, THEN take the work up on the same branch". The correct
behaviour is neither idle nor premature: hold the mutation, do read-only prep, acknowledge.

- Do NOT create a worktree, branch, claim, or push off the PRE-wait head. The head you can
  measure right now is the one the other lane is about to rewrite; cutting/claiming off it
  races that lane, produces a churn commit, and sets up a duplicate-vehicle collision the
  rebase then orphans. A branch that reads `MERGEABLE` at the old head is not licenced to act.
- In the wait window do only read-only work: read the issue/PR body in full, run the scope
  research, confirm the current wire state (`gh pr view --json state,headRefOid,mergeable,isDraft`,
  `gh api repos/<o>/<r>/branches/<branch>`), and note the head you are waiting on.
- Acknowledge to the dispatcher ONCE with the sequencing you will follow ("holding: taking up
  <task> on <branch> only after your rebase-lane lands its head; I will post the claim + report
  branch/head when I begin"), so the planner sees you received it and know you are not stalled.
- Take the work up only after you can prove the other lane's head LANDED: `git ls-remote` ref
  equals `gh pr view --json headRefOid`, and it differs from the pre-wait head. Then claim and edit.
- A "WAIT" dispatch is NOT a stale-gate to correct and NOT a stale-PR to withdraw — do not
  "settle" it by pushing, and do not de-scope or reopen anything to look busy. Holding IS the action.

## Direction G — a peer's coordination ANSWER is itself a timed measurement (permission may be moot)

A peer lane replying "the branch is free, I am not holding it — go ahead and add X / push when
ready" has measured the branch at THEIR read, and answered a question you asked earlier. Treat
the answer as a claim, not a licence: the work it grants permission for may already be at the
head. Measure in the same turn, before any edit:

```bash
git ls-remote <remote> refs/heads/<branch>          # is my commit already on the remote?
gh pr view <n> --json headRefOid,mergeable,mergeStateStatus
```

If the remote ref equals the PR head and that head IS your commit (the peer's quoted shas are its
PARENTS), the permission is moot — reply "already landed at `<sha>`, nothing to push" and push
nothing. Never manufacture a push to consume a granted permission, and never re-commit the same
content onto the head to "take up" work that landed before the DM was sent.

In the same reply, state SCOPE OWNERSHIP explicitly: name the part of the branch you own
(test-only fixture, docs-only change) and say a base rebase is the **branch owner's** call. A peer
writing "it is yours-or-the-owner's call" must not pull a rebase onto your lane when you are not
the branch owner and were not dispatched for it — declining that half is correct, not a stall.
Also correct any premise of your own that the thread has superseded (e.g. "the guard red is
by-design" once a reviewer write-back has cleared it) in ONE short note.

Post the conclusion on the PR/issue thread in addition to the DM — a decision that exists only in
a DM does not exist for the next reader. Bookend it as the thread already expects: measured head
sha, what you did (nothing to push / nothing touched), what remains and whose call it is.

## Direction H — a peer asks you to CONFIRM a dispatch "landed" (report the receiver-side effect)

A planner/reviewer asks "did the re-dispatch land — confirm the reviewer actually received my
message `<id>`" (and may distinguish it from an earlier id it also cited). The message id is a
SENDER-side artifact you cannot re-derive or verify; auditing which id went out is a dead end.
The proof that the reviewer received AND APPLIED the evidence is the RECEIVER-side effect on the
wire: the acceptance criterion is ticked `[x]` carrying the exact replayable
`command + rc=… + run=… + head=…` you handed over, or the prescribed edit is present at the live
head. Read that and report it as the confirmation:

```bash
gh issue view <n> --json body --jq .body | grep -n 'failure in job'   # AC ticked + evidence form?
gh api "repos/<o>/<r>/contents/<path>?ref=<live-head>" --jq .content | base64 -d | grep -n <prescribed>
```

Reply shape: "the tick is live on #<n>/the edit is at `<sha>`, so whichever id carried it, the
reviewer applied it." Do NOT chase the id, and do NOT re-send the evidence because the peer
misremembers which id it was — a re-send on an already-applied dispatch is noise, and it restarts
a delivery lag the peer will then re-quote back at you (its next settled pass may still show the
stale value it generated before consuming your correction — that lag is not a disagreement).

## Direction I — a peer asks YOU for all-clear to force-push a branch you do NOT own (verify the claim, route to the owner, never release another lane's hold)

The inverse of Direction G. A rebase/merge lane messages you "you own branch X — confirm it is clear for
me to force-push my rebased head" — but you may not own the branch at all, and it may carry a live hold
that is not yours. Read the `bot-claim:` comment BEFORE accepting the role:

```bash
gh api repos/<o>/<r>/issues/comments/<claim-id> --jq '"by="+.user.login+"\n"+.body'   # who the claim NAMES
gh pr view <n> --json headRefOid,baseRefName,mergeable,mergeStateStatus,state
```

- If the claim names a DIFFERENT lane (e.g. `bot-claim: llgenie-engine-improver`), you are NOT the owner
  and cannot grant the push all-clear. Correct the premise once, name the real owner, and route the
  decision to that lane — never answer "clear to push" on a branch you do not own. Being the lane whose
  stacked PR was folded into the branch does not make you its owner.
- A live TTL hold placed by ANOTHER lane (`<!-- bot-claim: <lane> <ts> <work> ttl=240m -->` "leave it
  alone for the next 4 hours", often a `run-failure-reactor`/`github-actions[bot]` marker) is NOT yours to
  release, even when the peer explicitly asks you to. A `bot-claim` is a lock the claiming lane owns; only
  that lane or the planner can lift it. Report its `ttl`/expiry, say the hold must stand, and never waive
  another lane's hold to unblock a push.
- Before confirming anything, check whether YOUR stacked PR was already squash-merged INTO the base
  branch — your separate branch ref may be GONE because it was consumed, and your content now lives in
  the base history. Confirm by ancestry, not by the vanished ref (`couldn't find remote ref` is the
  consumed signature, not damage):
  ```bash
  git fetch origin <base-branch>
  git merge-base --is-ancestor <your-fold-sha> origin/<base-branch> && echo "my content is in the base"
  ```
- What you CAN confirm: that you will not push the branch (single-pusher, #824), and that your content
  survives a base-refresh rebase (merge-tree rc=0 + the file present at the fetched head). Then HOLD — the
  go/no-go belongs to the branch owner AND to the holder; state both.

## Pitfalls

- A dispatch can cite COMMENT IDs (e.g. "full scope on comment 66…") that do not resolve on any
  issue/PR from your side yet — the lane may still be landing them, or they live in the sender's
  own session. That is not a blocker: fall back to the dispatch text + the issue/PR body, which
  carry the scope; say once that the cited comment is not yet retrievable and that you will
  re-read the thread before your first edit. Do not fabricate the comment's contents.
- `gh pr view --json` with a jq expression that concatenates a string field fails
  (`cannot add: string and object`) — query fields individually or use `gh api`.
- Do not hand-write a live profile file to "sync" a tree-only lint blank; that is the owning
  lane's `make sync-agent-profile` job and not a gate class.
