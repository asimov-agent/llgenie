# rebase-bot-dispatch-pr-input

## ADDED Requirements

### Requirement: the rebase-bot dispatch can be aimed at one PR

`.github/workflows/rebase-bot.yml` must expose an optional `pr` `workflow_dispatch` input with no
default, and `scripts/rebase_bot_sweep.py` must accept `--pr <n>`. When `--pr` is set, the sweep
evaluates only that PR; when it is unset, the board-wide sweep is unchanged. All decision
invariants apply to an aimed run exactly as to a sweep: daily cap, draft/base/head-owner checks,
merge-state and direct staleness measurement, bot-claim coexistence, never-merges, and the
actor's `--force-with-lease` push to the PR's own head remote.

#### Scenario: an aimed run decides only for the target

Given open PRs #1 (oldest, BEHIND) and #42 (behind, same repo), when the sweep runs with
`--pr 42`; then `action=rebase` names `pr=42` and #1 is never considered.

#### Scenario: an aimed run leaves an ineligible target alone with a reason

Given target #42 whose measured lineage shows it is not behind, when the sweep runs with
`--pr 42`; then `action=none` and the printed reason names #42's measured state. The other
open PRs are not evaluated.

#### Scenario: an aimed run on a closed or off-main target names it

Given target #42 that is not open against `main`, when the sweep runs with `--pr 42`; then
`action=none` with a reason naming `#42`, exit 0.

### Requirement: an aimed run cannot weaken a guard

An aimed dispatch must keep the guard job ahead of any secret-bearing step, must skip a PR held
by another bot's live claim, must never merge, and must cap at `max_per_day`; the unset path
(board-wide sweep) must behave identically to before the input existed.

#### Scenario: a held target is passed over like any candidate

Given target #42 whose latest comments carry another bot's live claim, when the sweep runs with
`--pr 42`; then `action=none` names the claim as the pass-over reason.
