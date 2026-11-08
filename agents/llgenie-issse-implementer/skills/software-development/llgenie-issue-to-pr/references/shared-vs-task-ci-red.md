# Shared upstream CI red vs a task-relative red

A red check at your PR head is not automatically yours. Before diagnosing it, establish whether the failing workflow is green anywhere (main, sibling PR heads). A red that also hits main and every other open PR head is a shared infra/trigger defect — chasing it as a task-relative defect burns the session and tempts you to invent a change your diff cannot justify.

## Prove which one it is (in order)

1. **Does your diff touch the failing domain?** `git diff --name-only origin/main...HEAD`. A `ci.yml` / `.github/workflows/` failure with **zero** `.github/` files in your diff cannot be caused by you.
2. **Is the workflow file byte-identical to main?** `git show HEAD:.github/workflows/ci.yml | sha1sum` vs the same for `origin/main`. Identical → your branch carries main's exact workflow; any failure is inherited, not introduced.
3. **Does main fail it too?** `gh run list --repo O/R --branch main --workflow ci.yml --limit 5 --json databaseId,status,conclusion`. Failing on main confirms it is not PR-specific.
4. **Do sibling PR heads fail it too?** Run the same `gh run list --branch <sibling-branch>` for the other open PRs on the same base. The same red across unrelated PRs = shared.

If steps 1–4 all point to "shared", it is **not your lane**. Do not push a speculative change to green it.

## Recognize the trigger-failure shape

- `gh run view <run-id>` prints `X <job> · <run> ... This run likely failed because of a workflow file issue.`
- `gh api repos/O/R/actions/runs/<id>/jobs` → `{"total_count":0,"jobs":[]}` — the run never spawned a job.
- `gh run view <id> --log-failed` → `failed to get run log: log not found` — there is no per-PR log to diagnose.

That trio (workflow-file-issue message + zero jobs + no log) means the workflow failed to *start* — a trigger/eval defect, not a job that ran and failed. YAML-parse the workflow at your head anyway to rule out a syntax error you did introduce; if it parses and matches main, the start-up failure is upstream.

## What to do with it

- Post an **honest verdict** on the PR citing the four proofs above (no `.github/` in diff, ci.yml sha identical to main, main red, siblings red), name it the shared workflow-trigger class, and state which lane owns it (gate / workflow changes → ci-pipelines lane, not implementer).
- Route it where the work lives (issue/PR comment) instead of inventing a task-relative fix.
- Do **not** present a shared red as green to arm on; do not force it green. The owner's merge gate decides.
- Still verify every PR-level gate that DID run and pass (guard / scope / holds) independently — a shared workflow red does not excuse skipping the gates that ran.

## Recovery after the routed gate fix LANDS: re-run the failed job, do not push

Once the owning lane's fix for a shared/routed gate defect merges to `main`, your blocked PR's
red does not clear by itself — but you also do NOT push, rebase, or rebuild to pick it up. The
classifier/gate reads **main's code at run time**, and a PR head untouched since the fix is still
evaluated by the OLD code until a run is triggered on it. Trigger the cheapest thing that re-
evaluates the same head:

- `gh run rerun <run-id> --failed` re-runs just the failed job(s) on the existing head against
  current `main`'s tooling. Get the run id from
  `gh api "repos/O/R/actions/runs?head_sha=<head>" --jq '[.workflow_runs[]|{id,name,conclusion}]'`
  and pick the failing one (e.g. the scope/classifier job).
- Confirm the fix is truly on main FIRST — `git show origin/main:<classifier>.py | grep -n <symbol>`
  and `git log --oneline -3 origin/main` (the merge commit). Do not trust a PR's `mergedAt`/`mergeCommit`
  field alone: it can read `null` while the merge has in fact landed; main's own log is the authority.
- Do NOT rebase a MERGEABLE PR just because main moved under it (rule #1015). A re-run clears a
  classifier red without touching history; a rebase churns shas and forfeits any pending verdict.
- Watch the re-run to completion (`gh run view <id> --json jobs --jq '.jobs[]|{name,conclusion}'`) —
  "in_progress" is not a pass; report the merged verdict, not the trigger.

This is the paired recovery to the "not my lane, route it" verdict above: route → owner merges →
re-run the blocked head. A re-run of the same head is also the correct recovery for a `cancelled`
deciding run (see `references/worktree-and-run-safety.md`), never a rebuild.

## A build-matrix cell red: prove the fix's own marker before calling the AC failed

When the acceptance evidence is a build-matrix sweep and a cell reds, open THAT cell's own
job log and grep it for your change's own marker line (the printed note the fix emits on
its branch). If the marker is present, the tolerance worked and the red is downstream —
never report it as "my fix failed".

- A cell that shows your cold-build/skip path ran and then died at **exit code 143** was
  SIGTERM'd by the runner (shutdown / cancel, often a wall-clock cap on a heavy multi-GB
  build) — not a defect your diff introduced. Say so; do not attribute it to the change.
- A build-dependency error inside a third-party project the repo does not track (e.g. a
  vendored upstream's `pyproject.toml`/poetry gap) is outside the vehicle's file set:
  record it as an upstream/out-of-scope red, name its owner, and do not widen your PR to
  patch a file you do not own.
- Record the sweep honestly as "N/M done, K red (with the real error line per red; the
  fix's tolerance verified working on every red cell)" and do not tick or close on it —
  the reviewer's verdict needs a green run at the rebased head.

## Re-read PR state before a long diagnosis

The owner can merge the PR while you are mid-diagnosis. Before spending minutes fetching logs, `gh pr view <n> --json state,mergeStateStatus` — a `MERGED` state means stop diagnosing and verify the merge landed on main instead of chasing a log for a branch that already shipped.
