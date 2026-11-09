# Stale-base reds and the rebase handoff

Diagnosis and the ONE rule that governs who acts on a stale-base red.

## A `linux/unit` / `ci-unit` red with GREEN pytest is a hygiene gate, not a test

`make ci-unit` runs the suite AND then host-side gates. A `NNNN passed, NNNN deselected` pytest summary followed by a non-pytest error means the failure is one of: `check-pr-base` (#845, a stale base), the import-roots ratchet, or lint. Read the job LOG; do not re-run the tests.

## `check-pr-base` = stale base

It reds when canonical `main` advanced past your branch's base. Log shape: `merge-base with origin/main is <old>, not origin/main itself`, `measured against origin/main at <new>`. The branch sat on a stale tip and the gate correctly refuses it — a stale base, not a code defect.

## The remedy is a rebase — but this lane does NOT run it

**This lane does not rebase ANY PR, its own pipeline-fix PR included (owner instruction 2026-10-30: `llgenie-pr-merge-conflict` owns rebasing ongoing PRs).** On a stale-base `check-pr-base` red the action is a handoff, not a rebase:

1. Post the measured stale base on the PR — the old base sha, the current `upstream/main` tip (`git fetch upstream main`; `git rev-parse --short upstream/main`), and the `check-pr-base` log line that names both.
2. Notify `@llgenie-pr-merge-conflict` with the PR, branch, measured head, and the stale base/tip pair.
3. Do NOT close the PR and do NOT re-run the red run — the red is nullified by the rebase push the other lane makes, never by a rerun.

The rebase itself (`git rebase --onto upstream/main <old-base> <branch>`, refresh `AGENTS:`/`BASE:` to the NEW tip in BOTH the commit message and the LIVE PR body, then `--force-with-lease`) is the rebase lane's to run.

## Local pre-flight (state the rebase lane can trust)

Verify the base is genuinely stale before reporting (a false stale-base claim sends a lane to rebase a branch that is already cut correctly): `python3 scripts/check_pr_base.py check --base <upstream-main-tip-sha> --rev HEAD` and require `[check-pr-base] OK: HEAD is cut from <sha> (merge-base == base)`; plus `git merge-base HEAD <upstream-main-tip>` printing that same sha. If it prints OK, the red you saw was at an older head — re-measure, do not report a rebase.

## The race is STRUCTURAL, not bad luck

`linux/unit` runs ~14 minutes while canonical `main` merges faster, so a rebase can go stale again before its own matrix finishes (measured: the base advanced several times inside one PR's life, each advance re-redding the same gate on an otherwise all-green suite). Planning consequences:

- Do NOT start a rebase while a matrix is in flight on that branch — `cancel-in-progress` would destroy a possibly-green run, and the target is stale by the time it concludes anyway.
- The rebase lane must target the sha from a `git fetch upstream main` taken in the SAME minute as its push, never a sha from an earlier fetch or a peer's message.
- When the same `check-pr-base` red reappears after a rebase, that is the expected shape — re-measure the tip, do not go hunting a code defect in the gate or the tests.
- The green pytest summary IS the proof the SUITE is fine, so report the red as "hygiene gate, base stale" with the log lines, never as a failing test.
