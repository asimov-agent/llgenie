# Cutting, rebasing and re-measuring the branch base

## The base gate wants the current tip, not the sha you were dispatched with

`check-pr-base` reds when the branch's base is behind live main. A dispatch that names a base sha is a snapshot: main can merge again while your run is queued, and the gate then fails on a branch that was correct when it was cut.

The remedy is a **rebase onto the live tip** — not an argument with the gate, and never a force-push of a branch another lane repaired.

```
git fetch origin refs/heads/main:refs/remotes/live/main --force
git rebase --onto refs/remotes/live/main <old-parent-of-your-commit> <branch>
git push --force-with-lease --force-if-includes origin <branch>
```

`--force` on the fetch is required (a bare fetch is silently rejected as non-fast-forward once `live/main` exists and has moved — see `base-and-merge-integrity.md`), and the explicit `--onto` form is the safe one: it cannot mis-compute the fork point. A plain `git rebase <tip>` lets git pick the fork point, and can flatten your commit — see below.

Cross-check the fetched ref against the API before quoting it, because a fork's `origin/main` can lag the true tip:

```
gh api repos/<R>/commits/main --jq .sha
```

The two values must match. The explicit refspec plus the API read is the only pair that cannot silently drift.

## A base-field retarget is not a rebase — measure the merge-base, not the `base` field

A dispatch that says "base `<sha>` == live main, base-race cleared" is describing the PR's **`baseRefOid` field**, which is a pointer, not a measurement. Changing that field (retargeting the PR base to an older main) does **not** move the branch, does not re-trigger CI, and does **not** clear `check-pr-base` if main has advanced again since: the gate keys on `git merge-base(<head>, fresh origin/main) == origin/main tip`, not on the PR's declared base.

So before trusting "base-race cleared", run the two reads that cannot lie:

```bash
git fetch --force origin refs/heads/main:refs/remotes/origin/main
H=$(git rev-parse <head>); M=$(git rev-parse origin/main)
git merge-base --is-ancestor "$M" "$H" && echo "chains main tip ✓" || echo "base-drift persists"
git log --oneline "$M".."$H"        # foreign commits ⇒ head did not incorporate main tip
```

A retarget to `X` while live main is `Y` (`Y` a descendant of `X`) leaves merge-base == `X` ≠ `Y`, so the gate still reds — the fix is a rebase **onto the current tip `Y`**, not a base change. Cross-check the fetched ref against `gh api repos/<R>/commits/main --jq .sha` in the same breath; they must match the tip you rebase onto.

## A plain rebase can flatten your commit — name the range with `--onto`

`git rebase <tip>` makes git compute the fork point itself; when that computation decides your commit is already "upstream" it replays **nothing** — it prints "Successfully rebased", resets the branch ref to the tip, and your commit is gone from the branch (the object survives in the reflog). Never read "Successfully rebased" as "my commit is on top": verify `git rev-parse HEAD^` equals the tip and `git rev-parse HEAD` is your own commit, not `HEAD == tip`.

Name the replayed range explicitly so git cannot mis-fork:

```bash
git fetch origin refs/heads/main:refs/remotes/live/main --force
git rebase --onto refs/remotes/live/main <old-parent-of-your-commit> <branch>
```

If it already flattened, recover from the reflog and redo with the explicit form — do not re-commit from scratch:

```bash
git reset --hard <pre-rebase-head-sha>
git rebase --onto refs/remotes/live/main <old-parent> <branch>
```

## Main can merge more than once inside one long CI leg — the same red repeats

The unit leg runs ~14 minutes and the fleet keeps merging during it, so a `check-pr-base` red can fire **again at the next head** for the same reason: main advanced past the tip you rebased onto while that run was in flight. Two or three consecutive `check-pr-base` reds in one session are the **same race**, not three new defects — do not file anything against the PR for it. Handle each identically: re-fetch `--force`, re-point the body twin lines, rebase, push, and re-quote at the new head. The only durable exit is the fleet quiescing long enough for one run to conclude at a tip that is still current; say so in the report rather than presenting each red as a fresh failure.

## A rebase invalidates every base sha quoted in the PR body

After the rebase, re-measure whatever the body pins to the base and update it in the same breath:

- the `BASE: <sha>` twin line, and whatever the parallel `AGENTS:` line measures (bytes / lines of the agents file at that sha) — the file content may be unchanged while the sha in the body is now wrong;
- any `SYNC:` line naming the profile that must be re-synced.

Re-run `git show <new-base>:<path>` for the measured numbers instead of carrying the old values forward: unchanged is a result you read, not one you assume.

## After a force-push, the old head's checks are not the new head's

A force-push starts a new run at the new sha. Until that run concludes there is **no verdict at this head** — quote nothing from the previous sha, and treat neither its red as inherited nor its green as earned.
