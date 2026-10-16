# bot-decision-loud — a crashed bot decision must fail the step, not read as "nothing to do"

## Why

Every bot workflow first asks a `make` target which subject to work on (`…-sweep`, `…-pick`,
`…-dispatch`). Three of them swallowed the answer, and the run concluded **green while the bot never
worked**:

- `rebase-bot.yml` (#310, fixed) — `action=${action:-unknown}` → `go=false`; the bot had never rebased
  a PR.
- `issue-refiner.yml` (#316, fixed) — the same shape on `make issue-refiner-pick`; the bot had never
  refined an issue.
- `issue-bot.yml` (**still live**) — the dispatch step captures `rc=$?`, writes it to `GITHUB_OUTPUT`
  and **never consults it**. A crashed dispatch leaves `action` empty, `[ "$action" = "cap" ] ||
  [ "$action" = "none" ]` is false, so `dispatch=true` and the run marches on to the JEV gate, the
  smoke, triage and implementation with **no issue picked**.

`fix-bot.yml` is already safe (`set -euo pipefail` with the `make` call as the step's command).

The reason this recurs: a `grep` for a guard is not proof of one. `set -e` in the wrong place, an
`exit 0` at the end of the step, or an rc that is captured but never read all look guarded.

## What Changes

- **`issue-bot.yml`'s dispatch step fails on a crashed decision**, naming the target and its rc
  (`::error::the issue-bot's decision failed (make issue-bot-dispatch rc=7); refusing to treat a
  crashed decision as 'nothing to pick'`).
- **A table-driven test pins the rule for every bot workflow** (`tests/test_bot_decision_loudness.py`,
  wired into `test-unit`). It does not grep: it takes each step that runs a decision target, **runs
  that step's own shell** against a `make` on `PATH` that exits 7, and requires the step to exit
  non-zero. The step's script is the product under test; `make` is the external command, stood in for
  the same way the `gh` tests stand in for `gh`.
- The same file asserts the rule's SCOPE is read from the tree (so a new bot workflow is covered the
  moment it exists), substitutes a `${{ … }}` the way the runner does (so the loudness test cannot
  pass because bash tripped on an expression), and proves the other direction — a decision that
  answers cleanly leaves the step green.

## Impact

- `.github/workflows/issue-bot.yml` — the dispatch step gains the rc check.
- `tests/test_bot_decision_loudness.py` (new), `Makefile` (`test-unit`).
- No behaviour change for a healthy run: a decision that exits 0 takes exactly the path it took
  before.

## Not covered

- The per-bot crashes themselves are fixed by their own changes (#310/#316, and this one for
  `issue-bot`); this change is the shared loudness rule and its guard.
- The `triage` / `verdict` / `impl` steps of `issue-bot.yml` deliberately record an rc in
  `GITHUB_OUTPUT` and let the NEXT step's `if:` gate on it — that is a signal, not a swallowed
  decision, and changing it would alter how a failed agent step ends the run. Out of scope here.
