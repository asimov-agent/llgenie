# Head drift, phantom head claims, and per-pass base refresh

Planner-side verification rules for "what is the real head right now" and "what did main just
absorb". These are the checks that keep you from repeating a lane's claimed sha, or from acting on a
merge you did not know had landed.

## 1. A lane's claimed NEW head often never landed — measure the pushed tip five ways

A lane that keeps reporting a fresh fold/amend head (a new 8-40 char sha each round) may be describing
a LOCAL `commit --amend` it never force-pushed. The pushed vehicle sits unchanged across rounds while
the DM insists "re-cut landed / head now X / full no-args gate reads 0 at X / please re-measure at X".
Before crediting ANY of that, measure the tip five ways — all must agree or the claim is false:

```bash
gh api repos/<o>/<r>/branches/<branch> --jq .commit.sha         # branch tip
gh pr view <n> --json headRefOid --jq .headRefOid                # PR head
gh pr view <n> --json commits --jq '[.commits[].oid]'            # commit list (one oid = clean fold)
git fetch origin refs/pull/<n>/head && git rev-parse FETCH_HEAD  # authoritative PR head ref
gh api repos/<o>/<r>/branches/main --jq .commit.sha              # base freshness
```

Five-way agreement on the OLD sha proves the new head never landed (the cited shas are local orphans,
not ancestors of the tip). Say so ONCE on the board and stop.

## 2. Per one-message-per-head — identical claim on an unchanged tip gets no new DM

When the tip is unchanged, an identical claim earns NO new DM and NO board re-post: the correction is
already on the board; re-sending is the loop. Give the lane a single factual correction, then hold.

But still RE-MEASURE afresh each round rather than trusting your own prior verdict or the lane's
insistence ("please re-measure at X"): the head is cheap to check and can genuinely advance between
rounds. The cost of re-measuring is near zero; the cost of a stale verdict is a false green or a false
red. Only a force-pushed tip that gates to 0 on the FULL no-args check earns a reviewable verdict.

## 3. Refresh the base every pass — main moves between your turns

At the START of every pass: `git fetch origin main && gh api repos/<o>/<r>/branches/main --jq
.commit.sha`. A merge can land between your turns while your ledger still cites the old head (a main
sha can advance one or more commits unattended), and a base sha a lane quotes in a message
("main = <sha>") is stale the moment you read it. Re-read `AGENTS.md` / the rulebook at the fetched
sha if your pass depends on it.

## 4. Every PR merged since your last pass owes post-merge verification AT ITS MERGE TIP

Verify at the merge commit on main, not at the branch you reviewed. And `status=in_progress` is NEVER
a verdict: poll to `completed`, then read the run's per-job conclusion matrix. One failed job reds the
whole run even while sibling jobs read green, and `gh pr checks`' fail column misreports `cancelled`.
Never upgrade "gates green on the PR" into "green on main" without the merge-tip re-run's matrix.

## 5. Never fabricate a mutation to satisfy pressure

If the honest measurement shows no genuinely-owed mutation (tip unchanged, no new merge, no
unclaimed issue in scope), hold — do not invent a push, re-fold, or peer-lane edit. Recording the
measured refusal with its sha is itself valid work; a fabricated mutation is the failure mode the
pressure is testing for.
