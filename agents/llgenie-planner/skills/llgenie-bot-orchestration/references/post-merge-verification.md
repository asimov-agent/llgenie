# Post-merge verification: a merge is not a completion

**Every merged PR must be re-verified after the merge.** A green pre-merge PR proves the branch passed the gates **at that head on that base**. It does not prove:

- the squashed result on `main` is green (a squash can drop a trailing commit; a merge can collide with another PR merged minutes earlier),
- the issue's acceptance criteria are actually met on `main` (a stacked PR "merges" into its parent branch, not into `main`, so nothing reaches `main` at all),
- the change did what it claimed once combined with everyone else's.

## The pass (run it for every merge, oldest first)

```bash
# 1. what merged, and into WHAT (base matters more than state)
gh pr list --state merged --limit 20 --json number,title,mergedAt,mergeCommit,baseRefName
#   baseRefName != main  ⇒ it merged into a parent branch; its content reaches main only when THAT merges

# 2. is main itself green at the resulting tip?
M=$(gh api repos/<o>/<r>/commits/main --jq .sha)
gh api repos/<o>/<r>/commits/$M/check-runs --jq '[.check_runs[]|{n:.name,c:(.conclusion//.status)}]|group_by(.c)|.[]|"\(.[0].c): \([.[].n]|join(", "))"'
#   any in_progress ⇒ acceptance is UNVERIFIED, not verified. Say so and re-check.

# 3. do the issue's acceptance criteria hold on main?
#   read the issue, then measure each criterion on main — not on the PR head
```

## Failure handling

If main is red at the merge tip, or a criterion does not hold:

1. **First: attribute the reds to their culprit before filing anything.** Several failing guard/tests
   in one whole-tree re-run usually trace to **one** file. Read the assertion bodies, not just the
   `FAILED` names — e.g. a "cron slots collide" guard and a "guards not byte-identical" guard can
   both name the same workflow file. When every red points at one culprit, ask one question: does an
   **existing open issue already diagnose that culprit?** If so, **append** the failing tests, their
   `file:line`, and the run id to that issue as widened acceptance evidence ("this fix must also
   clear tests X and Y, not just Z") — do **not** open a parallel tracker for the same file. One file,
   one issue; a duplicate tracker splits the fix and lets the second guard stay red after the first
   lands. File a **new** issue only when the reds trace to a culprit no open issue names.
2. **File a new issue** (do not reopen the merged PR — its history is closed and its diff is now `main`'s).
3. Name the merged PR, its merge commit sha, the exact gate/criterion that fails, and the run id proving it.
4. **Delegate** it to the lane that owns that surface, with the acceptance condition spelled out.
5. If `main` is red, that is the highest priority on the board — every open PR inherits a broken base.

**Reproduction belongs in the test image, not a bare `pytest`.** The unit suite runs under a `make`
target that drives the `$(TEST_RUN)` container image (python + pytest + deps mounted at the repo).
A bare `python3 -m pytest` on the host fails `No module named pytest` — that is the harness being
absent, **not** "cannot reproduce" and not a reason to doubt a log a lane posted. Run the make target
(or reproduce in that image) when you want your own confirmation; otherwise attribute from the failing
assertion body and the `FAILED` lines the lane's log already contains.

## When the check-runs read is empty, prove the red from the source

`commits/<sha>/check-runs` can come back empty (quota, retention, or a leg recorded under a
merge-queue ref) even for a merge whose leg genuinely failed. Empty is **not** green — it is
"unmeasured". Do not fall back to the merge event either (an owner merge through a failed leg
leaves `MERGED` in place). Prove the red from the source instead:

```bash
git show origin/main:Makefile | grep -nA3 '<gate-target>'     # which script the leg actually runs
git show origin/main:scripts/<gate>.py | head -40             # what the gate counts/refuses
git show origin/main:<file the PR added> | grep -nE '<the refused shape>'   # the delta itself
```

A set/count ratchet makes attribution mechanical: it refuses when the recorded site-set grows, so
a file the PR added that contributes new sites **is** the red, and naming its `file:line` is the
evidence. This is stronger than a log tail (which proves a leg red without saying whose) and it
costs one `git show` — never run the full containerized suite to prove it. Then file the tracked
issue naming the merge sha, the run id, the gate target, and the offending `file:line`, and hand it
to the lane that introduced the file; a red its own change caused is not a lane-boundary crossing
when that lane is asked to fix it. Expect the lane to retract any "green" it already claimed — a
retraction is the correct behaviour, not a correction to argue with.

## The stacked-PR trap, measured

On one night three PRs reported MERGED while their `baseRefName` was another lane's branch, not `main`:
`#1032` and `#999` merged into `feat/agent-profile-implementer-skill`; `#1045` likewise. **Nothing of theirs was on `main`.** A board that counts them as landed overstates progress, and reverting the base branch would look like a regression on `main` with no cause. Always read `baseRefName` before crediting a merge.

**The converse error is the same trap from the other side: `baseRefOid` is the base the branch was opened/pushed against, NOT its merge base — a stale `baseRefOid` on an already-`MERGED` PR does NOT mean "not rebased".** Reading `baseRefOid: d94d3280` and concluding "the rebase never landed, cannot adjudicate" is wrong when the PR is in fact `MERGED`: the merge landed on current `main` regardless of what the field still names. Before calling a PR unlanded or stale-based, read `state`, `mergedAt`, and `mergeCommit.oid` — a MERGED PR's `mergeCommit.oid` is the fact (it can equal current `main`), and confirm landfall with `git merge-base --is-ancestor <merge_commit> origin/main`. `gh pr view <n> --json state,mergedAt,mergeCommit --jq '{state,mergedAt,merge:.mergeCommit.oid}'` is the one read that settles it; `baseRefOid`/`baseRefName` are for the stacked-parent question only, never for "did it land".

