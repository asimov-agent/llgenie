# Verifying a planner claim against canonical git

Planner reports arrive as DMs from `@llgenie-planner`. They are measurements made in
*their* environment, and that environment can differ from yours. Before acting on a
claim that a branch is missing, a run never happened, or a PR is unmerged, **re-measure
against the canonical repo yourself**. Two failure modes are common and both cost a
wrong action if taken on trust.

## 1. `origin` may not be canonical

The canonical remote is `asimov-agent/llgenie`. A fork named `origin` is **not** upstream.
A planner `git ls-remote origin refs/heads/<branch>` returning EMPTY can simply mean their
`origin` points at a fork, or their snapshot predates the push. Verify with an explicitly
canonical query:

    git ls-remote https://github.com/asimov-agent/llgenie refs/heads/<branch>
    gh api repos/asimov-agent/llgenie/git/ref/heads/<branch> --jq .object.sha

If that returns a sha, the heads-ref exists and there is nothing to "restore".

## 2. A stale head is not the vehicle head

GitHub stores the PR's *current* head in `headRefOid`; an older sha (often the first red
push) still resolves via `refs/pull/<n>/head` only while it is the head. If the planner
measures `actions/runs?head_sha=<old>` and reports `total=0`, first check whether that sha
is the superseded v1 commit. Measure the real vehicle head:

    gh pr view <n> --repo asimov-agent/llgenie \
      --json state,mergedAt,mergeCommit,mergedBy,headRefOid \
      --jq '{state,merged_at:.mergedAt,merge_sha:.mergeCommit.oid,merged_by:.mergedBy.login,head:.headRefOid}'
    gh api "repos/asimov-agent/llgenie/actions/runs?head_sha=<headRefOid>" --jq '.total_count, (.workflow_runs[]|{id,name,status,conclusion})'

A red run on the dead v1 sha is historical and irrelevant once the head moved and merged.

## 3. Merged is the state that ends the question

Before re-pushing, re-arming, or "restoring" anything, read `state`. If `state:MERGED`,
the work is landed: a re-push resurrects a dead commit or races the merge, and arming is
moot. The repo's own auto-merge (actor `asimov-agent`) lands approved green PRs — that is
not a lane self-merge. Record the proving facts, not the badge: `state`, `mergeCommit.oid`,
`mergedBy.login`, `mergedAt`, the green run id at `headRefOid`, and
`git cat-file -e upstream/main:<path>` for the file that was supposed to land.

## 4. "Unclaimed / no branch / no PR / assignees ()" is not proof of no vehicle

A planner board that keeps re-forcing an issue as "unclaimed, branchless, no PR" may key
on `assignees`, which stays empty for a lane whose bot id is **not a GitHub login**.
`llgenie-ci-pipelines-maintainer` (the bot's id) is not an assignable user — a
`POST /issues/<n>/assignees -f assignees=llgenie-ci-pipelines-maintainer` returns 200 but
leaves `assignees:[]`. Do not "prove" the claim by assigning a human; prove it by the
vehicle link GitHub already synced:

    gh issue view <n> --repo asimov-agent/llgenie --json closedByPullRequestsReferences \
      --jq '{closingPRs:[.closedByPullRequestsReferences[]|{num:.number}],assignees:(.assignees|length)}'

a `closingPRs:[{num:<pr>}]` entry means the PR cross-links the issue as its closer — a
single, authoritative vehicle, regardless of `assignees:0`. (`closingIssuesReferences` is
not a valid `gh issue view` field; use `closedByPullRequestsReferences`.) Post one
API-quoted comment on the issue naming the PR + the measured head, then **stop** — do not
DM-argue the same stale read past ~3 corrections (no-ping-pong / max-3 discipline). The
issue comment plus the synced closer-link is the durable record; a looping planner board
does not change it.

## 5. "The single open vehicle" may be a CLOSED PR — list ALL PRs before you force-push

A planner force-push directive can name the wrong vehicle. It may call a **closed** PR
"the single existing open vehicle" (and even cite a head sha that does not match that
branch's live tip), while the branch it names was pushed under a *different* closed PR and
the actual open implementation is a separate PR entirely. Conflated issue/PR numbers and a
closed-PR branch are both real. Before any force-push, enumerate every PR touching the
issue and read each `state`:

    gh pr list --repo asimov-agent/llgenie --state all --search "<issue#> in:body,title" \
      --json number,state,headRefName,headRefOid,title \
      --jq '.[]|"PR#\(.number) \(.state) \(.headRefName) @\(.headRefOid[0:8]) \(.title)"'
    gh issue view <issue#> --repo asimov-agent/llgenie --json state,labels --jq '{state,labels:[.labels[].name]}'

A force-push onto a CLOSED PR's branch does **not** reopen the PR and cannot "keep it as
the one vehicle" — it is a dead branch. If exactly one PR is OPEN, that one is the vehicle
and there is nothing to force-push; state the measured contradiction to the planner (PR#,
state, head, branch-tip-vs-stored-head mismatch) and hold. Never force-push on a premise
`state:CLOSED` disproves.

**Your OWN vehicle can be closed unmerged while the issue still ships through a broader vehicle — verify the live one rather than reopening yours.** An owner consolidating, or a wider PR superseding your narrow one, leaves your `state:CLOSED` + `mergedAt:null` yet the issue delivered. Confirm the LIVE vehicle carries your fix: `gh pr diff <live> | grep '^diff --git'` for the file you fixed, read the trigger/guard at its head (`git show m<live>:<path>`), and run ITS guard tests on ITS tree (see `verification.md` §8). Report the measured board (live vehicle + head sha + passing guard + any residual red, which may be a shared tracked defect). Do NOT reopen your closed PR beside an open one (duplicate vehicle), edit the owner's branch, or invent a commit/change-note to look delivered.

## 6. A held "aligned / nothing owed" state EXPIRES the moment a merge lands — re-measure the tip every time

The most expensive error is not a wrong measurement, it is a **stale one that felt settled**. A
multi-turn "aligned, serene, nothing owed" hold is only true at the sha it was measured at: a
merge on trunk (a census/scope/unblock fix landing, any PR the fleet was waiting on) moves
`origin/main` past the base of every open PR, so a PR that read `MERGEABLE` an hour ago now reads
`CONFLICTING`/`DIRTY` with green head checks. Never re-assert alignment from memory, a prior
comment, or a chat-quoted sha. Before any "still aligned" reply, re-measure the moving parts:

    git ls-remote <canonical> refs/heads/main        # canonical tip RIGHT NOW (no local-ref ambiguity)
    gh pr view <n> --repo asimov-agent/llgenie --json mergeable,mergeStateStatus,headRefOid,baseRefName

The tell that a hold has silently expired: the PR's own head check-runs are all green yet GitHub
says `mergeable:CONFLICTING` — that is never a failing test, it is a rebase-against-new-trunk
conflict. Confirm the intersect and route it:

    git diff --name-only <old-base> <head> | sort > /tmp/h
    git diff --name-only <old-base> <new-tip> | sort > /tmp/m
    comm -12 /tmp/h /tmp/m                          # the exact conflicting path(s)

Report the finding on the PR (head + intersect + canonical tip), then hand the rebase to the
rebase lane and tell the planner — do NOT rebase it yourself (rebase is another lane's job).

## 7. Ambiguous local refs poison merge-base and rev-list — measure with explicit SHAs

A local ref name can resolve to two different objects (`refs/heads/prNNN` vs
`refs/remotes/prNNN`), and git prints `warning: refname 'prNNN' is ambiguous` yet still returns
*an* answer — often a contradictory one: `merge-base` and `rev-list --count` against the same
symbolic name disagree because each subcommand resolves it in a different namespace. Two rules:

- For the trunk tip, use `git ls-remote <canonical> refs/heads/main` (a sha, never a local ref).
- For the PR head, take `headRefOid` from `gh pr view`, then compute divergence on the **full
  SHAs** the API and ls-remote returned, not on branch names: `git merge-base <headSha> <mainSha>`
  and `git rev-list --count <mainSha>..<headSha>`. `git merge-base --is-ancestor <mainSha> <headSha>`
  is the one-bit answer to "behind vs on-top".

Also: `origin` on this host is the **fork** (`andyholst/llgenie`); canonical is `upstream`
(`asimov-agent/llgenie`). Fetch/resolve the canonical tip from `upstream`, never `origin`.

## Rule

Never act (push, arm, delete, restore) on a planner anomaly you have not reproduced
against `asimov-agent/llgenie`. Reply with the sha-bound measurement — PR state, real head,
the green run id, and the merge sha — and let the planner correct their board. A planner
model that loops or a fork-`origin` snapshot does not change canonical truth.

**Measurement hygiene:** the shell's persisted cwd can point at a temp worktree you (or a
prior run) already removed, so every command dies at `cd` with exit 126 before any git runs.
Pass an explicit `workdir` (e.g. `/tmp`) and drive git with `git -C <absolute-repo-path>`, so a
poisoned `$PWD` never masks a real measurement as a failure.
