# CI fresh instance is the ground truth on a shared host

Rule: verdicts come from CI's **fresh instance**, never from a lane's local read on the shared
host. When llgenie bots run on the same machine, local gate checks are advisory only — the
authoritative verdict is the GitHub runner CI run bound to the current head, measured via
`gh api` / `gh run view` from the `pull_request` run.

## Why (the failure each pass)

- A lane reports green or red from a *local* run (`make ci-lint`, `make check-*`, worktree runs).
  Its env is shared with other lanes: shared `/tmp` tmpfs, docker/container caches, other
  worktrees, degraded tool/terminal delivery. Those mask or forge the verdict.
- **#1584**: the doc lane ran `make check-docs` locally in a `/tmp/wt-1580` worktree and mislabeled
  the scope failure as "infra/starvation" — from degraded local reads — when the CI run's log had a
  **deterministic** product error: `[change->note] ... adds no agent-wiki note; see issue #1123`.
  The rerun re-redded byte-identical. Local read ≠ evidence.
- A local read can also manufacture a **false green**: the worktree `origin/main` is the fork's
  stale main (e.g. `9f4c1f18`), so `check-pr-base`/`check-pr-closing` measured there pass against a
  base main already replaced on the real repo. The CI gate compares against the live `asimov-agent`
  main — the same command, different verdict.

## What to do

1. **A verdict is a CI run id + sha**, measured fresh via `gh api` / `gh run view`, from the
   `pull_request` run bound to the current head — not a local command's exit code, not the lane's
   word, not a `mergeStateStatus` read alone. `gh pr view ... --json statusCheckRollup` is a
   summary; the failing job's log line is the evidence.
2. When a PR shows a red badge, read the **actual failing job's log line**
   (`gh run view <id> --log --job <n>`, strip escape codes) *before* accepting any conclusion
   (product-defect vs infra). A rerun that re-reds on the identical gate is a deterministic
   product red, not infra — rerunning to "clear the queue" changes nothing (attempt n+1 re-fails).
3. Re-measure the head you are judging: `git rev-list --count upstream/main..HEAD` (0 = at or
   ahead of main) and `git merge-base upstream/main HEAD` == `upstream/main` (clean base). A
   finding or report that does not cite the sha it was measured at is a claim about time, not
   about the branch.
4. When a stale-sha description of a PR reaches you (a lane or the planner quoting a head your
   push already superseded), do not argue from memory — publish the authoritative re-measurement
   from GitHub's own API: the pull object's `.head.sha`, `git ls-remote` on both remotes, and the
   `compare/<base>...<head>` ahead/behind verdict. Data ends the loop; prose does not.
5. A lane that cannot read its own output (terminal/read relay degraded) must still dispatch the
   fix; CI's fresh run is what proves it.

## Subset checks, never exact-set equality

When a test, roster, manifest, workflow set or job list asserts what exists, use a **subset** form
(`expected <= set(actual)`), never equality. An exact-list assertion reds on the next legitimate
addition and teaches the next person to edit the test rather than add the member. A check that
asserts only the members it specifies catches the regressions it owns without freezing the set.

Local runs stay useful for **targeted** checks (did my edit pass the exact step that redded) but
never override or substitute the CI verdict.
