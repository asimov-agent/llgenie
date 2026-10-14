# issue-implementer

## ADDED Requirements

### Requirement: at most one issue implemented per day-slot, capped at 3 a day

The bot MUST enforce a hard, checkable cap of **3 issues implemented per UTC day**,
counted from GitHub itself (`gh search prs --repo <repo> --author <bot>
--created ">=<today> 00:00Z"`), before any work starts. When the count is
already 3 or more, the run MUST log `cap reached: N/3 today, next issue
tomorrow`, exit 0, and change nothing — no comment, no issue, no PR. When the
count is below 3 it MUST take exactly ONE issue and stop; it never implements a
batch.

WHEN the bot's daily count is 3 THEN a further attempt logs the cap, exits 0 and changes nothing.
WHEN the count is 2 THEN it takes one issue and stops.

#### Scenario: the cap boundary is a named test

- **Given** a bot that already opened 3 PRs today
- **When** `dispatch` runs
- **Then** it exits 0, logs the cap, and the fake `gh` recorded no claim comment and no issue open
- **And** with only 2 opened today it proceeds to claim one issue
- **Test:** `tests/test_issue_implementer.py::test_cap_reached_at_three_exits_zero_and_changes_nothing`
- **Test:** `tests/test_issue_implementer.py::test_below_cap_it_claims_one_issue`

### Requirement: pick one issue, defined deterministically

The bot MUST pick exactly ONE issue: labeled `agent:implement` first (oldest
label first), else the oldest open issue labelled `agent:ready`. It MUST claim
it with a marker comment AND a most-recent-event check so a second concurrent
run cannot grab the same issue, and MUST derive the branch name
`agent/issue-<n>-<slug>` (the slug from the title, lowercased, non-alphanumerics
to `-`, trimmed to a bounded length). The issue's title and body MUST be written
to `issue.md` for the agent to read.

WHEN there is a labelled `agent:implement` issue THEN it is picked before any `agent:ready`.
WHEN two candidates exist THEN the oldest label is picked first.
WHEN the picked issue was just claimed by another run THEN the run stops without double-claiming.

#### Scenario: picking and claiming

- **Given** an open `agent:implement` issue (older) and an open `agent:ready` issue (newer)
- **When** `dispatch` runs below the cap
- **Then** it chooses the `agent:implement` issue, writes `issue.md`, emits branch `agent/issue-<n>-<slug>`, and the fake `gh` recorded the claim comment argv with the issue number
- **And** when only `agent:ready` issues exist it chooses the oldest of those
- **Test:** `tests/test_issue_implementer.py::test_it_picks_a_labeled_issue_and_claims_it`
- **Test:** `tests/test_issue_implementer.py::test_it_falls_back_to_the_oldest_ready_issue`

### Requirement: the PR links the issue, says what was verified, never merges

The PR the bot opens MUST be draft-free, MUST link the issue (`closes #<n>` or
`Implements #<n>`), MUST state what was implemented and what was verified and
what was not, and the bot MUST never merge it and never push to `main`.

WHEN the PR is opened THEN its title and body reference the issue number and its base is `main`.

#### Scenario: opening the PR

- **Given** an implemented branch `agent/issue-11-fix-thing`
- **When** `open-pr` runs with the issue number and the body
- **Then** the fake `gh` recorded `pr create` with `--base main`, the branch, and the title/body including `#11`, and the PR URL is returned
- **Test:** `tests/test_issue_implementer.py::test_open_pr_links_the_issue_and_never_merges`

### Requirement: the dispatcher is real, no-mock, and wired

The dispatcher MUST be a real executable the product starts as a subprocess —
only the GitHub API is a stand-in, so the tests assert the exact request the
product builds (the `gh`-on-`PATH` shape, as in `tests/test_engine_skill_gap.py`).
The new `scripts/issue_implementer.py` MUST be reachable from a make target, and
`tests/test_issue_implementer.py` MUST be named by `make test-unit`, so neither
is a dead document (AGENTS.md wiring rule).

WHEN a new script or test file is added THEN it is named by a make target or workflow step, never dead.

#### Scenario: the wiring holds

- **Given** the Makefile and the issue-bot workflow
- **When** the wiring is checked
- **Then** `scripts/issue_implementer.py` is reachable from `make issue-bot-dispatch`, the workflow calls real make targets, and `tests/test_issue_implementer.py` is in `make test-unit`
- **Test:** `tests/test_issue_implementer.py::test_the_dispatcher_and_tests_are_wired`
