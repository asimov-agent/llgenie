# Repair a red PR with the fix-bot, then re-check

## Why

When a PR goes red, the branch waits for a human to read a log, work out whether the code or the
test is wrong, fix it and push — and AGENTS.md's own gates (no skipped tests, no mocks, Makefile
-driven verification) mean whoever picks it up has to know the house rules. The sibling repo
`andyholst/trending-local-llms` already runs a fix-bot that closes that loop; llgenie's CI is
different (matrices, engine images, a wiring guard), so this models it rather than copying it.

Issue #222 specifies the behaviour: the fixer MAY update a failing test, but only when that test
exercises real business logic, and it must never mock the system under test, weaken an
assertion or silence a gate. Fixing the code is the default.

## What Changes

- **`scripts/fix_loop.sh`** — the bounded loop: run the failing check (`make ci-unit` by default),
  hand the rules plus the failure output to the agent, re-check, up to `FIX_ROUNDS` (default 3).
  Exit 0 = green, 1 = still red (leave it for a human), 2 = misconfiguration. It **never commits,
  pushes, merges, rebases or touches `main`** — the workflow publishes, and only on green.
- **`scripts/fix_bot_rules.md`** — the contract with the agent: fix the code, never mock or
  weaken, verify through the Makefile, do not edit workflows to change an outcome, no
  credentials in files.
- **`scripts/fix_bot_report.py`** — the PR comment when the loop gives up (the command, the
  fenced tail of the report, and the fact that the bot leaves it for a human).
- **`.github/workflows/fix-bot.yml`** — `workflow_dispatch` only (no `workflow_run`: a
  bot-authored PR must not re-trigger the bot), concurrency per PR/branch, an owner/write-access
  guard, PR resolution that refuses `main`, checkout and push with the owner PAT (so CI re-runs
  on the new head), one commit, a PR comment, and `timeout-minutes: 120`.
- **`ci.yml`'s `dispatch-fixbot` job** — on `failure() && pull_request && same-repo && !draft`,
  dispatch the bot with the failing check, capped by counting the bot's own `fix(bot):` commits
  (3), so a repair that does not stick cannot loop.
- **`scripts/install_hermes_ci.sh`** — the Hermes install seam (already installed → install
  script URL → `uv tool install`), a loud failure otherwise: a fix-bot without an agent must not
  silently report "still red" forever.

## Capabilities

- **pr-fix-bot**: a red same-repo PR is repaired automatically within a bounded number of
  attempts, with the results reported on the PR, never merged, and never at the cost of a
  mocked/weakened/skipped check.

## Impact

- The loop and the reporter are hermetic-tested (a stub agent on `PATH`, a real loop): rounds,
  early stop, loud give-up, misconfiguration, and "the loop touches no git".
- `make fix-loop` is the local entry point; the workflow is the CI one. Nothing is merged by a
  bot, and no credential is written to a file.
