# Acceptance verdicts are blocked until the guard reaches the heavy rows (#2049/#1696, 2026-11-07)

## The failure mode
A PR can carry a documented fix and the maintainer can cite a pass count, yet NO completion verdict is
owed because the head's guard run aborts BEFORE the heavy rows that prove the acceptance criteria ran.
When `check-pr-agents-line` (or `check-pr-base`, or any early hygiene gate) fails, the guard `Makefile`
step chain skips `linux`/`ci-images`/`scanner-images`/`engine-pins` and the heavy hermetic + network rows
never execute at that head. An `in_progress` producer run (e.g. `engine-build-pr-trigger`) is also not
completed. A verdict cited against such a head is fabricated — there is no completed run to name.

## The rule
Before claiming an AC pass (or `[x]` tick), verify the head has a COMPLETED run whose guard reached and
passed the heavy row that the criterion names. Concretely, at the judged head:
1. `gh api repos/<r>/actions/runs?head_sha=<sha>` and read every workflow run's `conclusion`;
   `cancelled`/`in_progress`/`null` = NO verdict.
2. If the guard run is red on an early hygiene gate, read its job steps: a `skipped` `linux`/`engine-pins`
   row after the failing gate means the heavy ACs were never measured — say **BLOCKED, no completed head
   run**, do NOT pass them off the PR body's "145 passed" claims.
3. `{name,conclusion}` of the job steps is the ground truth; the PR body's counts are claims.

## Exact gate wording that blocks (body-hygiene, author's fix, not the reviewer's)
- `check-pr-agents-line`: body must carry `AGENTS: <sha> <bytes>b <lines>l` (from `make bot-preflight`)
  — a PR with NO `AGENTS:`/`BASE:` lines at all, or a `BASE: <sha> (== origin/main at rebase …)` that
  fails the gate's exact `(== origin/main at open)` shape, aborts the guard. Issue #792 / #845.

## What IS provable off-blocked
When the heavy rows are skipped but the hermetic unit file is runnable locally, name it explicitly as a
LOCAL executable proof (command + rc + sha) for the AC it covers, and keep the network/live-Hub ACs
explicitly **NO VERDICT** until a completed run at head exists. A partial verdict (AC-3 proven, AC-1/AC-2
no verdict) is honest; a full pass off an un-run head is not.

## Unblock condition (name it on the PR)
Fix the `AGENTS:`/`BASE:` body lines so the guard proceeds, then a COMPLETED run at the head proves the
heavy/network ACs with a citable run id. Never approve or merge when the head run is red on an early gate
or still in_progress (#1088).
