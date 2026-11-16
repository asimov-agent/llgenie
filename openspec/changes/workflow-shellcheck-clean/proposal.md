# Proposal: workflow-shellcheck-clean

## Why

`make check-workflows` enforces only the class of defect that makes GitHub REJECT a whole workflow
file (unparseable `${{ ... }}`, missing newline, missing `name:`, bad `workflow_run` roster, bad cron).
Shellcheck and section-syntax findings inside accepted files pass silently by design, so they re-report
on every audit and no gate can forbid new ones. Measured on `main` (`f45268c84`) with the digest-pinned
`rhysd/actionlint@sha256:b1934ee5…` (v1.7.12): **16 shellcheck findings across 12 workflow files** plus
**1 syntax-check finding** (`concurrency.queue` in `engine-build.yml`) — issue #329's original list of 7
findings is stale relative to the tree; the live set is these 17.

## What Changes

- Fix all 16 live shellcheck findings: quote expansion in `run:` scripts (SC2086/SC2046), group
  consecutive `>> file` redirects into one `{ …; } >> file` (SC2129), move `${{ … }}` out of
  single-quoted printf format strings (SC2016), `printf` instead of `echo` for escape-bearing text
  (SC2028), and restructure the `ENFORCE=` assignment (SC2209).
- KEEP `concurrency.queue: max` in `engine-build.yml` — it is load-bearing per issue #2294 (the queue
  key is what stopped cancelled producers; GitHub accepts the key; actionlint 1.7.12 has not catalogued
  it). The gate passes exactly one narrow `-ignore` regex naming that message, so the exception is
  documented and cannot grow.
- Extend `make check-workflows` with a chained `check-workflows-shellcheck` step that runs the digest-
  pinned actionlint full ruleset over `.github/workflows/`, so the debt class cannot come back.
- Test-pin the wiring: the chain exists, the image is a digest pin (not `:latest`), the `-ignore` is the
  single documented queue-key regex, and the Makefile surface is declared.

## Impact

- Affected specs: `check-workflows` (ADDED requirements)
- Affected code: `.github/workflows/*.yml` (12 files), `Makefile`, `mk/gates.mk`,
  `tests/test_workflows_valid.py`, docs (agent-wiki + changes.d fragment)
- No behavior change to any bot lane: every fix preserves the resolved values the step consumes.
