---
name: ci-scope-verdict
about: a cancelled CI fan-out is a "no verdict" failure, never the same row as a skip the scope decided
status: active
---

# A cancelled fan-out is not a legitimate skip (issue #1111)

## Proposal

A run's check-runs answer "which jobs reported, and with what conclusion". They cannot answer the
question a reader actually asks — **"was a job allowed to be missing?"** — because the decision that
selected the jobs lives in a different place from the conclusion that reports them. So a cancelled
fan-out and a deliberately skipped job produce the same row, and the field every board line quotes
(`failed=0`) reports both as clean.

Measured on run **41134761297** (`CI`, head `0bd5ac6e`, `conclusion=cancelled`): `guard success`,
`ci-images cancelled`, `scanner-images cancelled`, `linux skipped` — and **no `linux / unit` row at
all**, because `linux` is a reusable-workflow caller and it was skipped when `ci-images` was
cancelled. The check-runs for that sha were `success=3, failure=0, other=5, pending=0`. The same class
of change at `d92ee6a3` (run **41126873965**) reported `linux / unit | failure`, so the gate did exist
and did have an answer one head earlier.

## Motivation

`0 failures` is the number every lane and every board line quotes, and it was quoted for a head whose
unit gate never ran — and that head was armed with no unit verdict at all. The defect is not that a
run can be cancelled (that is `cancel-in-progress` working as designed); it is that the cancellation
leaves **no trace that a decision is owed**, so the absence of a verdict reads exactly like the absence
of a need for one.

The other half matters just as much: a skip that the scope decision DID make (a `tests/**` diff does
not need `install`, `agents-read`, `openspec` or `cpu-health`) must stay legal and green, or the gate
becomes "run everything for every diff" — the full matrix #824 exists to remove.

## Change

- **The decision becomes data.** `scripts/ci_scope.py::decision()` renders the classifier's answer
  (schema `1`) and `--decision-out` writes it; `ci.yml`'s `guard` job runs
  `make ci-scope BASE=<base.sha>` (or `ALL=1` for a push, which keeps the full matrix) and uploads it as
  the `ci-scope-decision` artifact with `if-no-files-found: error`.
- **The verdict reads it back.** `scripts/ci_scope.py::verify()` holds a finished run's job rows to
  that decision: a selected job that is `skipped`, `cancelled`, `pending` or absent is `no_verdict`
  (red); a job the decision did not select that is skipped is `skipped_by_decision` (green); no
  decision at all is `none` (red). The summary prints `verdict=…` and, when it is not green,
  `NO VERDICT: N job(s) unaccounted for — 0 failures is not a verdict`.
- **A consumer that survives cancellation.** `.github/workflows/ci-verdict.yml` is a `workflow_run`
  on `CI`/`completed` — any conclusion, because a cancelled run cancels its own jobs and no terminal
  job inside it could report. It runs `make ci-verdict` (`scripts/ci_verdict.py`), which reads the run,
  its jobs and the artifact through `gh`, applies the same SUPERSEDED test `scripts/ci_requeue.py`
  uses (a later run of the same workflow on the same branch), and writes the
  `POST /repos/{owner}/{repo}/check-runs` body. The workflow posts it, so the answer appears as a
  `ci-verdict` check-run on the head: `failure` for `none`/`red`, `neutral` for a superseded head,
  `success` only when every selected job reported and every skip is one the decision made.
- **Nothing is skipped by a condition.** No job-level `if:` is added anywhere
  (`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` allows none for a path selection), and
  the `["none"]` placeholder rows already on `main` are unchanged.
- **The red is routed.** `ci-verdict.yml` is named in `run-failure-reactor.yml`'s roster, so a red
  verdict is treated like any other red run instead of being a control nobody watches.

## Acceptance

- [x] A cancelled fan-out with **no** decision is `verdict=none` and its check-run conclusion is
      `failure`; the summary contains `0 failures is not a verdict`.
- [x] A cancelled fan-out **with** a decision names the selected jobs that never reported and is red.
- [x] A skip the decision made is green, is counted as `skipped-by-decision`, and is named.
- [x] A measured `linux / unit failure` run stays red and names the gate.
- [x] A head a later run of the same workflow superseded is `neutral`, never `success`.
- [x] An artifact that exists but cannot be downloaded is exit 2 — never a `none` verdict.
- [x] The sabotage loop: plant the old behaviour (`verdict = GREEN` for a missing decision), watch 5
      tests / 9 assertions red, restore, watch 19 pass.
- [x] `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs`,
      `make check-pr-hygiene` and `make openspec-validate NAME=ci-scope-verdict` exit 0.

## Not covered

- The empty-diff contract (empty diff = every family, exit 0; unknown path = every family, exit 1) is
  untouched by this change.
- `scope.yml`'s job list is unchanged: a cancelled `scope` single job is visible as `cancelled` (which
  `gh pr checks` already renders as fail), so the artifact is published by `ci.yml`, whose fan-out is
  the one that was silent.
