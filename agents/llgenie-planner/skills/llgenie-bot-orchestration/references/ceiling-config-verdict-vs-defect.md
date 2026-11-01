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

## An AC blocked on an infra gate filed OFF the PR: accept the green subset, hold the cell under its issue

When a PR's acceptance criterion (e.g. AC6 "fully-green at head") cannot be met because a red cell is a **runner-infra** gate that has already been filed as its own issue (not a defect in this PR's diff), do not hold the whole PR hostage to an unrelated infra fix, and do not silently call it green. The honest routing:

1. **Split the verdict:** accept the AC on the **verified-green subset** (the cells this PR's diff actually governs), stating the cell count and run id at the exact head.
2. **Attribute every remaining red to its tracked issue** by name/number, confirming it is identical pre- and post-fix (same failure both sides ⇒ infra, not code) and that none is touched by this PR's diff.
3. **Formally hold the infra cell under its filed issue** — the PR's AC is "green except cell X, which is owned by #<n> and must re-confirm green once #<n> lands before any merge-of-this-PR is recommended". Record that caveat **on the PR** so the partial accept is not read later as a weakened AC.
4. Never let this become "merge it anyway" — the merge stays the owner's (#1088); you have only accepted the *verdict* on the code the PR owns.

Measured case: #1220/#1196 — 16 non-CUDA install-leg cells green at `abc1d3ac` (run-head==PR-head verified), cuda cell red only on missing NVIDIA CDI (filed as #1240, infra, identical pre/post-fix). Routed option (a): AC accepted on the 16 green cells, cuda formally held under #1240. The engine-improver offered (a) accept-subset vs (b) hold-for-infra; **the planner picks (a) with the on-record caveat**, because an infra gate with a tracked remedy is not an unowned defect.

## Fleet instances of this error

- Planner's own premise on #1167/#1170 ("rerun picks up 120") — corrected by the
  reviewer: a `pull_request` run reads the workflow at the merge ref, rerun replays 60.
- doc-maint on #1133 (base `adf2c4e1`, an ancestor of `f3fa4b90`, evaluate 60) —
  reached for `gh run rerun 41199216710`; planner re-routed to a rebase onto
  `5ad07fa9`.
