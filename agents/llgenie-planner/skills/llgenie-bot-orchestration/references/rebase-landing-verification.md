# Did the rebase actually land on current main?

A lane reporting "rebased onto main" is making a claim. Three reads settle it, cheapest first.

## 1. The pushed head's parent must be the current main tip

```bash
tip=$(git ls-remote origin refs/heads/main | cut -c1-40)   # or: git rev-parse origin/main
gh api repos/O/R/commits/<head> --jq '.parents[].sha'
```

A rebase onto an **intermediate** commit (the lane rebased onto an older main, or onto another
lane's tip) produces a head whose parent is that intermediate sha. It looks rebased, CI even runs
green on it, and every citation of gate results/proof boxes measured "on main" is false.

## 2. Containment: `compare`, not intuition

```bash
gh api repos/O/R/compare/<main>...<head> --jq '.status'   # ahead | behind | diverged | identical
```

- `ahead` — head contains current main; the re-anchor is real.
- `diverged` / `behind` — head does **not** contain current main, whatever the lane says. Re-order
  the rebase onto the tip explicitly and say the parent must equal it.

## 2b. "Live tip" is a moving target — re-measure `behind_by` at merge time

`compare main...head --jq '.behind_by'` is the decisive number, not `status`. A lane that rebases
onto the tip as it stood **this minute** is correct, and re-staled the instant any other PR merges
onto main afterwards (`behind_by` climbs to 1, 2, … while the head still contains the older tip).
So a "base == live tip, re-anchored" verdict has a shelf life of minutes: before accepting a PR as
owner-merge-ready, re-`git fetch origin main`, re-read `behind_by`, and if it grew, dispatch the
same lane to rebase `--onto` the **new** tip (the replay is usually clean — the intervening merges
touch files the branch does not). Never call a branch merge-ready on a `behind_by`/base read taken
before the last merge; quote the tip sha and `behind=0` from the read taken at review time.

## 3. Read the PR head ref, never `ls-remote` alone

```bash
gh api repos/O/R/pulls/<n> --json headRefOid,baseRefOid,mergeable,mergeStateStatus
```

A just-pushed branch tip can sit **ahead of the PR ref for minutes**: `git ls-remote` shows the new
sha while the PR still lists the old one. "The branch tip moved" is not "the PR was re-anchored".
Base (not head) still on the old sha is the stale-base signal; head still on the old sha with a moved
tip is a push in flight — report it as such, do not claim the re-anchor landed.

## Recording it

Record the corrected board truth on the issue the same minute you measure it, and if you already
posted the optimistic version, revise it in place rather than deleting or appending a contradiction:
state the observed shas, the parent/compare result, what is still owed (rebase onto the named tip),
and that no proof may be cited until a head sha with parent == current main exists. When a lane is
mid-flight, DM it the target sha and the exact check it must satisfy before reporting.
