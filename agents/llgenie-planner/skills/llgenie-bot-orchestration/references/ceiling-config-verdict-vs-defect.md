# A ~1h unit cancel is a CEILING verdict, not a defect — rebase, never (only) rerun

A `linux / unit` row cancelled at ~1h0m under the OLD 60-min ceiling is **not a code
defect and not a starved-runner** until proven otherwise — it is a config verdict
bound to the head's **merge ref**. A `pull_request` run evaluates `.github/workflows/
pipeline.yml` at `head merged into base`, so the timeout that applies is whatever
`pipeline.yml:78 (unit.timeout-minutes)` reads at the PR's **base**, not at main today.

The 120-min ceiling landed in `f3fa4b90` (#1175). Any PR whose `baseRefOid` is an
**ancestor** of `f3fa4b90` still runs under `timeout-minutes: 60` — even if it has the
latest head — and `gh run rerun` replays the **recorded** workflow file (60), so a
rerun of a ceiling-cancelled run is a second cancel.

## Measure before accepting a lane's "cancel / no verdict" report

1. `gh pr view <n> --json baseRefOid,headRefOid` — note the base.
2. `git merge-base --is-ancestor <baseRefOid> f3fa4b90` — if exit 0, the base predates
   the ceiling; the run evaluated 60.
3. `curl -s ".../raw/<baseRefOid>/.github/workflows/pipeline.yml" | awk 'NR==78'` —
   confirm `timeout-minutes` at that base.
4. `gh run view <id> --json status,conclusion,headSha` — quote a **completed** run at
   the head before calling anything green or red.

## Correct recovery (owning lane's move)

Fetch `origin/main` (now carries the 120 ceiling), **rebase** the PR branch onto it,
force-push `--force-with-lease` (their own branch), and let a fresh run evaluate at 120.
That is when a cancel becomes a real signal.

## When a genuine 120-budget run ALSO cancels at ~1h

Only then is it a starved-runner / capacity signal — escalate to the queue-shaping
ledger (#882/#1146/#1139). Never call a 60-config cancel that first.

## Fleet instances of this error

- Planner's own premise on #1167/#1170 ("rerun picks up 120") — corrected by the
  reviewer: a `pull_request` run reads the workflow at the merge ref, rerun replays 60.
- doc-maint on #1133 (base `adf2c4e1`, an ancestor of `f3fa4b90`, evaluate 60) —
  reached for `gh run rerun 41199216710`; planner re-routed to a rebase onto
  `5ad07fa9`.
