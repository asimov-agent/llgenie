# A run-failure reactor: a red run becomes a fix or a deduped issue

## Why

`fix-bot` (#222) is the only runtime failure handler and it is PR-shaped: it selects from
`gh pr list --state open` and filters on `gh pr checks`. Anything without an open same-repo PR is
invisible to it. Measured against current `main`:

| Failure source | Covered today? | By what |
|---|---|---|
| Open **same-repo** PR check red | yes | `fix-bot` (#222) |
| Fork PR check red | no | excluded by the sweep (cannot push a fork) |
| Red run on **`main`** (`push`) | no | nothing |
| Red **scheduled** bot run (`registry-sync`, `engine-bump`, `engine-bump-rebase`) | no | nothing |
| Red **publish** run (`ci-images`, `engine-image-*`, `install-published-*`, `published`) | no | nothing |
| Job stuck in `queued` | reported only | `queued-alarm` (#254) |
| Static pipeline problems | issue only | code-review bot (#269) |

No workflow in `.github/workflows/` carries a `workflow_run` trigger, so no bot reads a run's
conclusion. A merge that breaks `main` sits red until a human notices; a failed weekly
`registry-sync`/`engine-bump` run posts no issue and no PR; a failed GHCR publish is silent.

## What changes

- `scripts/run_failure_reactor.py` — the stdlib-only, no-LLM route decision. Given a completed
  failed run it decides: **Route A** — the run has a non-empty `pull_requests` whose head is in
  THIS repo and pushable → dispatch the existing `fix-bot` for that PR (reusing
  `scripts/fix_bot_sweep.py`'s eligibility rules, never duplicating them); **Route B** — no
  pushable PR (a red `main` push, a red scheduled bot run, a red publish job) → file exactly ONE
  issue, marker-deduped, labelled `agent:implement` so the issue-bot picks it up. It never
  repairs/commits/pushes/merges in Route B — it files.
- `make run-failure-reactor` — the one make path the workflow calls.
- `.github/workflows/run-failure-reactor.yml` — `on: workflow_run: types: [completed]` over the
  repo's own workflows. GitHub REQUIRES a `workflows:` list on a `workflow_run` trigger and refuses
  the whole file without one, silently (a 0-job run whose `name` is the file path), so the file
  names every workflow this repository owns except the reactor's own — which is also what makes a
  self-trigger loop structurally impossible.
- `scripts/check_workflows.py` — a new `workflow-run-refs` rule: a workflow file declaring
  `workflow_run` with no `workflows:` list fails `make check-workflows`, so the refusal above is
  caught in review instead of by a silent 0-job run.
- `tests/test_run_failure_reactor.py` — fake `gh` on PATH, real script, real argv asserted.
- `tests/test_workflows_valid.py` — the `workflow-run-refs` rule, both directions.
- README + agent-wiki entry in the same commit.

## The claim protocol (issue #286 follow-up, #279/#285)

The reactor is a **writer**: it dispatches a repair or files an issue, and both are subjects
another bot may already hold. So it joins `scripts/bot_claims.py`:

- **consult before picking** — `bot_claims.occupied(comments, RUN_FIXER, ttl=…)` on the PR it is
  about to repair; a fresh claim from another bot means "leave it, take the next failure".
- **claim before the first mutation** — for a PR, `claim_comment(RUN_FIXER, "fix", now, ttl=…)`
  on the PR *before* dispatching the repair; for a run on `main` there is no PR to claim, so the
  issue it opens is its own subject (it owns the subject it just created).
- **release when it ends** — the fix-bot's own workflow posts the `done` comment when the repair
  ends; the reactor's claim on a PR is released by the fix-bot's `done` comment, exactly as a
  fix-bot sweep claim is.
- **the TTL it announces is the TTL its readers honour** — it uses `PR_CLAIM_TTL` (4h), the same
  window the fix-bot and rebase-bot use, so a reader ages the claim by at least the repair's own
  budget.

## What does NOT change

Nothing about how work is implemented. The reactor composes the existing bots; it does not
duplicate their logic (one path per resource, AGENTS.md). It never repairs, commits, pushes or
merges in the file-issue path — the issue-bot owns implementation, the fix-bot owns PR repair.

## Deliberate limits (measured, so they are honest rather than aspirational)

- A **fork** PR is never dispatched: the token cannot push a fork branch, so the reactor leaves it
  to a human (the same rule `fix_bot_sweep.py` already applies).
- A run it **cannot diagnose** (a `gh` read fails, the run shape is unrecognised) is reported
  LOUDLY to stderr and the run exits non-zero — never silently dropped.
- The dedupe marker is `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (SHORTSHA = first 12 chars of
  the head sha), searched with `gh issue list --search ... in:body`. An OPEN issue already
  carrying the marker files nothing.
