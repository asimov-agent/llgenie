# A cancelled fan-out is not a legitimate skip — the scope decision becomes data (#1111)

Issue: [#1111](https://github.com/asimov-agent/llgenie/issues/1111) — `ci_scope: a cancelled fan-out
and a legitimately skipped job look identical on the board`. Branch `fix/1111-scope-cancel-vs-skip`,
cut from `origin/main` at `d5fb875c`. PR: this change's pull request (`closes #1111`).

## The measurement (re-read from the API, not from the badge)

Run **41134761297** (`CI`, head `0bd5ac6e`, `conclusion=cancelled`) reported exactly four job rows:

| job | conclusion |
|---|---|
| guard | success |
| ci-images | cancelled |
| scanner-images | cancelled |
| linux | skipped |

No `linux / unit`, `linux / lint`, `linux / install`, `linux / agents-read`, `linux / openspec`,
`linux / top-tier`, `linux / cpu-health` row existed **at all** — `linux` is a reusable-workflow caller
and it was skipped because `ci-images` had been cancelled. The check-runs on the same sha were
`success=3, failure=0, other=5, pending=0`: the number every board line quotes said "0 failures" for a
head on which the unit gate had never executed.

The same class of change at `d92ee6a3` (run **41126873965**) reported the full set with
`linux / unit | failure`. So one head proved the change was wrong and the next head proved nothing, in
the same shape that reads clean everywhere.

## Why a check-run and not "just fail the run"

Measured on `0bd5ac6e`: the check-runs for that commit are the CI run's own rows plus `scope` and
`holds`. A `workflow_run` run (which is the only kind of run that survives a cancelled upstream)
creates **no check-run of its own** on the commit — `auto-merge`'s completion run is absent from the
same listing. A consumer that only reds its own workflow would therefore still be invisible to every
check-run reader, so `ci-verdict.yml` posts its answer with `POST /repos/{owner}/{repo}/check-runs`
and holds `checks: write` for it.

## What changed

- `scripts/ci_scope.py` — the classifier's answer becomes **data**: `decision()` (schema `1`, written
  by `--decision-out`), `normalise_job_name()` (`linux / unit` → `linux/unit`, `top-tier (none)` →
  `top-tier`), `verify()` (the accounting) and `check_run_payload()` (the POST body). `verify()` has
  four answers and no fifth: selected-and-passed (success), selected-but-skipped/cancelled/absent
  (`no_verdict`, red), not-selected-and-skipped (`skipped_by_decision`, green), no decision at all
  (`none`, red). The `linux` caller row is **reported and never counted** — its `linux/*` children are
  the accounting unit, and counting the container reded every legitimate skip.
- `scripts/ci_verdict.py` — the consumer. Reads the finished run, its job rows and the
  `ci-scope-decision` artifact through `gh` (`CI_VERDICT_GH` names the binary a test drives), decides
  SUPERSEDED the way `ci_requeue.py` does (a later run of the same workflow on the same branch), and
  writes the check-run payload. A **missing artifact** is the `none` verdict; an artifact that exists
  but cannot be read is exit 2, never a quiet "nobody decided".
- `ci.yml`'s `guard` — runs `make ci-scope BASE=<base.sha>` (or `ALL=1` on a push, which keeps the
  full matrix) and uploads `ci-scope-decision` with `if-no-files-found: error`. No job-level `if:` was
  added anywhere; the `["none"]` placeholder pattern that already exists on `main` is untouched.
- `.github/workflows/ci-verdict.yml` — `workflow_run` on `CI`/`completed` (any conclusion), per-run
  concurrency group, `cancel-in-progress: false`, `checks: write`, and named in
  `run-failure-reactor.yml`'s roster so a red verdict is routed rather than uncounted.
- `Makefile` — `ci-scope` gains `BASE=`/`ALL=`/`DECISION=`; new `ci-verdict` target, both in `.PHONY`.

## Negative control (the sabotage loop)

The suite is `tests/test_ci_verdict.py` (19 cases: the four answers, the caller row, the placeholder
row name, the CLI's exit codes, the stub-`gh` API path, and the workflow wiring). To prove the tests
hold the fix rather than the tree:

1. planted the old behaviour — one line in `verify()`'s no-decision branch, `verdict = GREEN`;
2. `python -m pytest tests/test_ci_verdict.py -q` → **5 failed, 14 passed**, with **9 assertions
   firing** (the `verdict=none` case, the two distinguishability cases, the CLI's `rc == 1`, the
   superseded payload's `neutral`, and the API-path `rc == 1`);
3. restored the line → **19 passed**.

## Verification

- `tests/test_ci_verdict.py` 19 passed; `test_ci_scope.py`, `test_ci_concurrency.py`,
  `test_ci_images.py` (`test_no_ci_step_or_job_is_skipped`) and `test_workflows_valid.py`
  (`test_the_repository_roster_matches_the_workflows_on_disk`) together with it: **121 passed**.
- `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs`,
  `make check-pr-hygiene`, `make openspec-validate NAME=ci-scope-verdict` green.

## Open

The `ci-verdict` check-run on a **fork** head is the one thing a hermetic test cannot prove: the
workflow posts to `head_sha` of a commit that lives in the fork. It is verified on this branch's own
run (a fork head is what every PR here is), and a red verdict run is itself routed by the reactor, so
a permission surprise is loud rather than silent.
