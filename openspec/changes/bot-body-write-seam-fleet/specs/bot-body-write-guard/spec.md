# bot-body-write-guard

## ADDED Requirements

### Requirement: every body-replacing bot lane is wired to the seam, asserted fleet-wide

Every `.github/workflows/*.yml` step that REPLACES the body of an existing pull request (`gh pr edit` with
a body payload, a `gh api PATCH … pulls/<n>` carrying a `body` field, or `--body-file`) MUST route that
body through `make bot-body-write`. A workflow that never replaces a PR body and only appends (`gh issue
comment`, `gh pr comment`) is proven append-only by the same wiring test. `tests/test_bot_body_write_fleet.py`
asserts both facts over every workflow file, so a new hand-rolled body write in any lane is a test failure.

#### Scenario: the three replacement lanes route through the seam

- **Given** `engine-bump.yml`, `registry-sync.yml` and `semgrep-rules-refresh.yml`, the lanes measured on
  `main` to re-write an OPEN PR's body from a template
- **When** their steps are read
- **Then** each carries `make bot-body-write` for the body and no `gh pr edit` with a body payload; any
  title update stays a title-only `gh pr edit`

- **Test:** `tests/test_bot_body_write_fleet.py::test_replacement_lanes_route_through_the_seam`

#### Scenario: append-only lanes are proven append-only

- **Given** `issue-bot.yml` and `issue-refiner.yml` post only `gh issue comment`, and `rebase-bot.yml`,
  `engine-bump-rebase.yml` and `auto-merge.yml` carry no PR-body write at all
- **When** the fleet scan runs
- **Then** the scan classifies them append-only / body-write-free and the test records that classification
  against the measured set

- **Test:** `tests/test_bot_body_write_fleet.py::test_append_only_lanes_stay_append_only`

#### Scenario: a planted hand-rolled body write is caught

- **Given** the fleet scan applied to a workflow text that hand-rolls `gh pr edit … --body-file` without
  `make bot-body-write`
- **When** the scan reports findings
- **Then** the planted file is named as a violation

- **Test:** `tests/test_bot_body_write_fleet.py::test_a_planted_hand_rolled_body_write_is_caught`

