# fix-bot-sweep

## MODIFIED Requirements

### Requirement: the sweep may select a PR whose head is the allowlisted fork

`scripts/fix_bot_sweep.py` MUST take `--own-fork <owner>` and treat a PR as pushable when its head
repository owner is the base repository's owner **or** that allowlisted fork. Any other fork MUST
stay skipped, with the existing reason. `.github/workflows/fix-bot.yml` MUST pass
`OWN_FORK=andyholst` to the sweep.

WHEN every open PR comes from the repository's own fork
THEN the sweep still selects the red one instead of reporting "nothing to fix".

#### Scenario: an allowlisted fork PR is eligible
- **Given** an open, red PR whose head owner is `andyholst`, swept with `--own-fork andyholst`
- **When** the sweep runs
- **Then** that PR is chosen
- **Test:** `tests/test_fix_bot_sweep.py::test_a_pr_on_the_allowlisted_fork_is_chosen`

#### Scenario: a third-party fork stays skipped
- **Given** an open, red PR whose head owner is not the repo owner and not the allowlist
- **When** the sweep runs with `--own-fork andyholst`
- **Then** it is skipped as a fork that cannot be pushed to
- **Test:** `tests/test_fix_bot_sweep.py::test_another_fork_is_still_skipped`

### Requirement: the repair is pushed to the PR's own head remote

`.github/workflows/fix-bot.yml` MUST resolve the PR's head repository, check the branch out from
that remote, and push with `--force-with-lease` to it: `fork` for the allowlisted fork, `origin`
for a same-repo PR. It MUST still never push to `main` and never merge.

WHEN the bot repairs a fork PR
THEN the commit lands on the fork branch, and CI re-runs on that head.

#### Scenario: the push targets the head remote, not origin
- **Given** the fix-bot workflow
- **When** its resolve/checkout/push steps are read
- **Then** it records the head repository, adds a `fork` remote for it, checks the branch out from it, and pushes to `REMOTE`
- **Test:** `tests/test_fix_bot_sweep.py::test_the_repair_pushes_to_the_pr_head_remote`
