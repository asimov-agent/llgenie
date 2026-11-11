# A run-failure reactor: a red run becomes a fix or a deduped issue

The pattern for a bot that reacts to ANY failed CI run's conclusion (not just a
PR check) and routes it to a remedy. `fix-bot` is PR-shaped — it selects from
`gh pr list --state open` and filters on `gh pr checks`, so a red `main` push, a
red scheduled bot run, or a red publish job is invisible to it. The reactor
closes that gap.

## Trigger: `workflow_run` fires for EVERY completed run, including your own

`on: workflow_run: types: [completed]` fires for every completed run in the repo
— including the reactor's own run. The reactor MUST skip its own workflow or it
re-triggers itself forever. Match the own-workflow name as a substring so a
renamed display name still skips.

## The route decision lives in a stdlib-only script, never in a job `if:`

Put the decision in a no-LLM, unit-testable script (like `fix_bot_sweep.py`), not
in a workflow `if:` that can silently skip. Given a completed failed run:

- **Route A** — the run has non-empty `pull_requests` whose head is in THIS repo
  and pushable: dispatch the EXISTING `fix-bot` for that PR, REUSING
  `fix_bot_sweep.py`'s eligibility rules — never duplicate or rewrite them. A
  FORK-head PR must NOT be dispatched (the token cannot push it).
- **Route B** — no pushable PR (a red `main` push, a red scheduled bot run, a red
  publish job): file exactly ONE issue whose title names the workflow plus the
  failing job, and whose body carries the failing job, its step, and a tail of
  the failing log (`gh run view RUNID --log-failed`).

## Dedupe with a body marker, searched in:body

File nothing if an OPEN issue already carries the marker. Use a body marker like
`<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (SHORTSHA = first 12 chars of the
head sha), searched with `gh issue list --search ... in:body`. Label the filed
issue `agent:implement` so the issue-bot picks it up.

## A writer bot joins the claim protocol

The reactor is a WRITER (it files issues / dispatches fix-bot), so it must
consult claims before acting and write its own claim on the subject it takes,
exactly like the other bots — via the shared `bot_claims.py`, not a second
implementation.

## It never repairs in Route B — it only files

Route B files; it does not commit, push, or merge. The issue-bot owns
implementation, fix-bot owns PR repair. One code path per resource; no second
implementation of another bot's logic.

## A run it cannot diagnose is reported LOUDLY

A `gh` read that fails, or a run shape it does not recognise, goes to stderr and
the exit code is non-zero — never silently dropped.

## Test with a fake `gh` on PATH

Drive the real script with a fake `gh` binary on PATH and assert the real argv
it would run (dispatch / issue-create). This locks the route decision without
hitting the network.
