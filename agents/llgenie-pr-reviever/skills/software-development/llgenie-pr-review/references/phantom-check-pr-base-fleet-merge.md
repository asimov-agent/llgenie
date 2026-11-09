# Phantom `check-pr-base` red under fleet merges — read the failing leg's own log before attributing

Applies to any post-merge or chain-gate "main green" verification in this repo.

## Symptom

A post-merge CI run at a merge head concludes FAILURE even though the merged content is sound. The
failing leg is `linux/unit` → `make ci-unit` → the ONLY red gate is `check-pr-base` (#845); every
real gate (authors, closing, hygiene, openspec, agents-read, lint, install, cpu-health, top-tier,
images) is green. The log block reads:

```
[check-pr-base] FAILED: `HEAD` is NOT cut from `origin/main` — its merge-base with
`origin/main` is <the merge head>, not `origin/main` itself …
foreign commits (0):
  (no commits in base..rev)
measured against `origin/main` at <a LATER main tip>
```

**`foreign commits (0)` is the tell**: the gate's own output shows no foreign commit leaked, yet it
still reds. That is base-staleness, not a content regression.

## Root cause

`check_pr_base.py` runs late in the CI leg (10–30 min in). When sibling fleet PRs merge to `main`
DURING the run, `origin/main` advances past the run's own head before the gate executes; the gate
sees the head is not the current tip and reds — even though the head is a valid ancestor of the
grown main.

## Verify it is a phantom (never a real regression)

```bash
git merge-base --is-ancestor <merge-head> <current-main-tip>   # YES → content is on main
git log --oneline <merge-head>..<current-main-tip>             # later commits are sibling merges
git show <merge-head>:<graded/path>                            # content intact
```

The failing leg's own log must show `foreign commits (0)` and all real gates green.

## What NOT to do

- Never claim "main green at the merge tip" from a run that reds `check-pr-base` — a `failure` run
  is NOT green. Prove the phantom with the checks above before calling it one.
- Do not treat each sibling's phantom red as independently blocking; re-anchor "main green" to a
  run at a head that STAYS the tip long enough to finish (the fleet-complete main — all siblings
  merged, no more mid-run advancement).
- Do not hold a PR for a phantom alone; a hold belongs to the REAL defect if one exists.
- Do not forward a red as "another lane's drift" until the leg's own log is read — the exact gate
  text decides between base-staleness, a cold cache (e.g. `buildcache-cuda: not found`),
  cache-expected, or a genuine content regression.

## One-line rule

A post-merge/chain CI red that is ONLY `check-pr-base` with `foreign commits (0)` and a merge-head
still an ancestor of current main = phantom base-staleness from a sibling merge mid-run; re-anchor
the main-green evidence to the fleet-complete tip, never fabricate a green, and never blame content
without reading the failing leg's own log.
