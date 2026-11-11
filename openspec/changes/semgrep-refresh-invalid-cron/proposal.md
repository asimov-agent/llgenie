# Proposal: semgrep-refresh-invalid-cron

## Why

`semgrep-rules-refresh.yml` (merged via PR #2357, issue #2283) declares only `schedule` +
`workflow_dispatch`, yet since its first branch push every `push`/`pull_request` event in the
repository has produced a ghost run of it: `startup_failure`, zero jobs, named by its FILE PATH,
no log, no check-runs (issue #2472 — 186 measured ghosts, four named in the issue).

The mechanism is now MEASURED, not guessed. GitHub's own API answers, for that workflow:

    POST /repos/asimov-agent/llgenie/actions/workflows/semgrep-rules-refresh.yml/dispatches
    → 422: Invalid Argument - failed to parse workflow: invalid `cron` attribute "1 6 * * 15"

The cron `1 6 * * 15` puts `15` in the **day-of-week** field (valid `0-7`); the intended
schedule — the file's own comments say "monthly on the 15th 06:17 UTC" — is the **day-of-month**
field (3rd slot). A file GitHub's compiler refuses is the documented #330 failure class: every
event routed to it becomes a 0-job `startup_failure` run whose name is the path, the Actions
registry keeps the record labeled by the path (measured: workflow id `411779538`, name == the raw
path), the schedule can never fire, and `workflow_dispatch` is refused. This is why no legitimate
run of the refresh has ever existed, and why PyYAML, actionlint-class tooling and this repo's
expression guard all pass the file: only GitHub's cron parser rejects it.

## What Changes

- FIX the workflow's schedule: `1 6 * * 15` → `17 6 15 * *` (06:17 UTC on the 15th — the same
  intent the file's comments state, written into the field GitHub actually reads).
- CLOSE the guard gap: `make check-workflows` gains a `workflow-cron` rule — every
  `.github/workflows/*.yml` `schedule: - cron:` value must fit GitHub's cron grammar
  (5 fields; minute 0-59, hour 0-23, day 1-31, month 1-12, day-of-week 0-7 or SUN-SAT;
  `*`, lists, ranges, steps). The gate is stdlib-only like the rest of the guard.
- UPDATE the docs that record the broken cron (`docs/ARCHITECTURE.md` ×2) to the fixed value.
- PIN every case in `tests/test_workflows_valid.py`: the exact shipped bad cron is red, the full
  grammar accepted, and every cron this repository actually ships passes.

## Impact

Affected specs: `workflow-integrity` (ADDED: cron-grammar requirement; refresh schedule fires)
Affected code: `.github/workflows/semgrep-rules-refresh.yml`, `scripts/check_workflows.py`,
`tests/test_workflows_valid.py`, `docs/ARCHITECTURE.md`

Out of scope (separate concerns, unchanged here): whether GitHub's phantom registry record
`411779538` is reparsed cleanly once the file parses (measured post-merge as AC1/AC2 of #2472);
the 186 historical ghost rows are history, not deleted.
