# Measurement discipline: heads, adjacency, and stale snapshots

## Measure the head at the moment you assert it (fast-moving-branch trap)

A PR's head moves under you — between the read and the report, and between two lanes watching the
same branch. A red declared "at `<sha>`" from a sha quoted in chat, or read minutes ago, describes an
intermediate snapshot and manufactures a phantom failure the owner must then disprove; the same
stale class repeats on every fast-moving branch.

- Bind every finding to `.head.sha` fetched immediately before posting:
  `gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha` (or `gh pr view <n> --json headRefOid`).
- Take the base from that same read; never mix a fresh head with a remembered base.
- When another lane's head differs from yours, reconcile at the newest `.head.sha` either of you can
  fetch. Never re-assert the older one, and say which sha superseded which.
- A chain of shas on one branch (e.g. `020345e0` -> `8d018a6e` -> `ae317f62`) means every sha but the
  last is history: re-measure before repeating a verdict.

## A closing keyword is adjacent or it closes nothing

`closes #N` in prose, on its own line, is adjacent. `closes **#N**`, bulleted-inline, or buried
mid-sentence is not, and GitHub silently does not close. The guard enforces plain adjacency, so a
body edit that bolds the keyword turns a green closing gate red.

- Check the **PR body line**, not just the commit message, before calling a vehicle merge-shape-clean.
- On a red closing gate, read the body line first; the fix is usually one word of formatting, not code.
