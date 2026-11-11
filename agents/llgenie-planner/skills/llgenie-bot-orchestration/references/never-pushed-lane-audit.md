# Never-pushed lane: categorical fork audit before owner escalation

## Rule
When a lane claims it is "working on" an issue but no PR/branch/claim exists, do NOT re-dispatch or re-correct per-instance 6+ times. First run the categorical proof, then escalate once with the complete evidence.

## A "START"/"working on" comment is not a push — measure the ref, then explain any hold
A lane posting "rebase START (owner-ordered)" (or any "working on #N") is a statement of intent, not evidence the branch moved. Verify the ref before calling the work either landed OR stalled:
```
git ls-remote origin 'refs/heads/<branch>'      # or: gh api repos/<o>/<r>/git/ref/heads/<branch>
```
Ref still equals the pre-claim head while the START comment is already minutes old ⇒ nothing was pushed; the START is UNLANDED. Do not repeat "it is being rebased" from the comment alone.

Before calling that a stall, check for a legitimate HOLD: a live run still `in_progress` at the OLD head. A rebase/replay push force-updates the branch, and `cancel-in-progress: true` mechanically kills that run — including build cells (rocm/cuda) still building and any pending acceptance-witness cell — so a lane that started a rebase while a long cell runs is plausibly holding the push to avoid superseding it (never-push-through-a-live-run). Confirm the run status and the cell's bound: a long-bound cell with hours of headroom makes "push when it concludes" a long, non-abandoned window.

The owed mutation here is a STATUS OBSERVATION, not a re-dispatch: record (1) the START comment timestamp, (2) the ref unchanged, (3) the in_progress run/cell explaining the hold and its remaining bound, (4) that the owner directive is not yet satisfied on the wire. Never fabricate a rebase not pushed, never cancel the live run to unblock it, and do not re-dispatch a lane that genuinely started and is plausibly holding.

## The categorical proof (one `gh` pass, no scripts)
```
gh api --paginate "repos/<owner>/<repo>/branches?per_page=100&sort=updated" > /tmp/forkbr.json
# absence + freshness checks via python / jq
```
Conclusive outputs: (a) issue branch absent from ALL branches, (b) no branch tip commit moved at/after the branch's created timestamp, (c) zero PR for `head=<owner>:<branch>`.

## The inverse case: a branch with NO PR is an ORPHAN — measure it before you re-dispatch or re-open

A ref that exists and is ahead of `origin/main` with no PR is not "done" and not "never pushed": it is an
orphan vehicle. Work landed on the wire and then nobody opened the reviewable artifact, so it is invisible to
the merge queue, to auto-merge and to every reviewer scanning for work. Measure three facts, never one:

```bash
git ls-remote --heads origin | grep -c "issue-<N>\|/<N>-"                        # does a branch exist?
git fetch origin <branch> -q
git merge-base --is-ancestor origin/main origin/<branch> && echo 'on main' || echo 'NOT on main'
git rev-list --count origin/main..origin/<branch>                               # commits ahead
gh pr list --repo <o>/<r> --state open --search "#<N> in:body" --json number    # any open PR naming it?
```

Both the `in:body` search and the `--head <branch>` search are needed — a PR can name the issue without
being the branch, and a branch can carry a PR that never mentions the issue.

| Measured state | Verdict | Action |
|---|---|---|
| branch exists, ahead > 0, `NOT on main`, no PR | **orphan** | dispatch: rebase onto current `origin/main`, open the ready-for-review PR **from the same branch** (one vehicle — never a second branch) |
| branch exists, `on main` or ahead == 0 | already merged | report the merged sha; do not open a PR, do not rebase |
| no branch, no PR, no claim, `agent:implement` label | **gate-free** | dispatch as fresh work off current `origin/main` |
| branch exists + claim comment, no PR, head frozen | never-pushed / hold | use the start-vs-ref proof above |

An orphan branch cut from an older main carries a second trap: opening the PR without rebasing first reds
`check-pr-base` and the lane then burns a run on the base gate instead of its content. Fold the rebase into
the same dispatch and state the done-condition as "merge-base with `origin/main` IS `origin/main`".

## Vehicle census for an idleness pass: three buckets per open `agent:implement` issue

"Which lane is idle-capable right now" is answered by one cheap pass over the open `agent:implement` list,
not by reading issue bodies. For each id, collect claim comments, remote branches and open PRs, then bucket:

```bash
for i in <ids>; do
  pr=$(gh pr list --repo <o>/<r> --state open --search "#$i in:body" --json number --jq '.[].number' | tr '\n' ,)
  br=$(git ls-remote --heads origin | grep -c "issue-$i\|/$i-")
  c=$(gh issue view $i --repo <o>/<r> --json comments --jq '[.comments[]|select(.body|test("bot-claim"))]|length')
  echo "#$i pr=[${pr:-none}] branch=$br claims=$c"
done
```

- `pr` non-empty → has a vehicle; its state is a PR problem, not a dispatch problem.
- `branch=1, pr=none` → orphan (section above).
- `branch=0, claims=0, pr=none` → **gate-free and idle-capable** — this is the queue the never-idle rule
  requires you to force a lane onto, with the domain owner named in the dispatch.
- `claims>0, branch=0` → claimed-not-pushed; read the claim age and the comment thread before touching it.

Every dispatch in this shape posts the durable record as an **on-issue comment** carrying the base sha, the
scope, the out-of-scope list and the exact "done =" condition, and the DM repeats it *citing that comment id*.
The comment is the authoritative channel: a DM can be rejected (queue full) or hit its hop limit, the issue
comment cannot.

## 2026-11-03 warning pattern (planner session)
The llgenie implementer lane claimed (6 consecutive reports) it was working #1685, but: branch absent across all 209 fork branches, no commits ahead, no PR, no bot-claim, no lane comment; newest fork tips all predate 07:23Z branch creation. Meanwhile it kept referencing WRONG (already-merged/closed) PRs #1681/#1655 as "open in-flight." Conclusion: lane not reading live API + not producing assigned work. Escalated once to owner on #1088 with complete fork-scan evidence.

## Never
- Do not re-correct a lane more than once over the SAME impossible claim; escalate with proof on the owner thread (#1088).
- Do not trust "state=open" from a lane; the API `pulls/<n>` is the authority.
- Verify the FULL branch set, not a subset, before asserting "never pushed": a subset view can miss a renamed branch.
- The owner-visible escalation comment is the vehicle: `message_agent` to the owner may be impossible; a teammate is not the owner.
