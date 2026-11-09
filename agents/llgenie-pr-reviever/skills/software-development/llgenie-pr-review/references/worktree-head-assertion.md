# Assert the worktree HEAD before trusting its runs

A persisted per-PR worktree (e.g. `/tmp/wt<pr>`) can sit on an OLD pinned head after the
branch is force-pushed or re-cut. `docker run -v $PWD:/repo` measures whatever HEAD the
worktree is on — a green pytest at the stale sha is NOT evidence at the mergeable head.

## Mandatory before measuring

```sh
git -C <wt> rev-parse HEAD          # byte-exact compare with gh api PR head
gh api repos/asimov-agent/llgenie/pulls/<n> --jq .head.sha
```

If they differ: `git worktree remove --force /tmp/wt<pr>` (prune if the registration is
stale) and re-add at `refs/remotes/live/pr<n>`, then re-run the evidence. Live body files
(`live_*.md`) must be re-fetched at judgment time too, never reused across heads.

## Measured failure (2026-11-06)

`/tmp/wt1866` still pointed at `8ec7b4cb` (pre-rebase pin) while the re-cut head was
`b49aa626`; the first run reported "17 passed" at the WRONG sha. `git rev-parse HEAD`
showed the mismatch before any verdict was posted. `git worktree prune -v` cleared the
stale registration.

A content-move rebase (graded files differ, `git diff --quiet` rc=1) is a RE-JUDGE at
the new head, not a re-anchor — re-run tests + gate, then re-write-back the pins with the
new sha + a named CI run id.

## After a write-back unmask, read EVERY remaining red leg, not just the flip

Clearing the acceptance self-red and re-running the guard does not end the review. The
rerun can uncover reds the hold had hidden BESIDE the predicted base-drift — e.g. a
`ci-openspec` structural failure (the PR's own change spec without `## ADDED
Requirements` deltas / `#### Scenario:` blocks, `skip_specs: true` absent; #156 class;
measured 2026-11-06 on #1874). Rerun BOTH the guard and the scoping workflow at the same
head, read each `conclusion==failure` job's steps, and replicate any unfamiliar red
locally with the CI's own image before attributing it (comment id + lane route). The
verdict/write-back for the closed issue stands; the PR is simply not mergeable until the
unmasked red is fixed by its owning lane.
