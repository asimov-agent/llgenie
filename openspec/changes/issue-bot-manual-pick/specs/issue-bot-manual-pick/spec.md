# issue-bot-manual-pick

## ADDED Requirements

### Requirement: a manual dispatch with no issue number picks one issue itself

`issue-bot.yml`'s `workflow_dispatch` input `issue_number` MUST NOT be required. With no value the run
MUST take the same path as the schedule: the dispatcher applies the 3/day cap, picks the oldest
`agent:implement` issue (then the oldest `agent:ready`), claims it, and the verdict leg routes that one
issue to implement / refine / close. A supplied number MUST still pin exactly that issue.

WHEN a maintainer dispatches the workflow with no `issue_number`
THEN GitHub accepts the dispatch and the dispatcher receives no `--force-issue`, so it picks.

#### Scenario: the dispatch form does not require an issue number

- **Given** the workflow file at `.github/workflows/issue-bot.yml`
- **When** its `workflow_dispatch.inputs.issue_number` is read
- **Then** it is not required, its default is empty, and its description says that blank means the bot
  picks the oldest `agent:implement` issue itself
- **Test:** `tests/test_issue_bot_manual_pick.py::test_the_dispatch_form_does_not_require_an_issue_number`

#### Scenario: a blank dispatch reaches the picking path

- **Given** the workflow's dispatch step and the Makefile's `issue-bot-dispatch` recipe
- **When** `inputs.issue_number` is empty
- **Then** `FORCE_ISSUE` resolves to an empty string, the recipe omits `--force-issue`, and
  `scripts/issue_implementer.py dispatch()` therefore receives `force_issue=None`
- **Test:** `tests/test_issue_bot_manual_pick.py::test_a_blank_dispatch_reaches_the_picking_path`

#### Scenario: a supplied number still pins that issue

- **Given** the same dispatch step and recipe
- **When** `inputs.issue_number` is `1234`
- **Then** `FORCE_ISSUE` is `1234` and the recipe passes `--force-issue 1234`
- **Test:** `tests/test_issue_bot_manual_pick.py::test_a_supplied_number_still_pins_that_issue`

### Requirement: the form and the README state the same contract

The workflow's header block and the README's generated dispatch table MUST state that a blank
`issue_number` makes the bot choose, so the interface a maintainer meets says what the code does.
`make check-dispatch-forms` MUST stay green over the change (every input documented, the README table
current).

WHEN the workflow's header and the README table are read
THEN both say a blank issue number means the bot picks, and the dispatch-forms guard passes.

#### Scenario: the header and the README agree with the form

- **Given** the workflow header block and `README.md`
- **When** the blank-means-pick wording is looked for
- **Then** both carry it, and `check_dispatch_forms.check` exits 0
- **Test:** `tests/test_issue_bot_manual_pick.py::test_the_header_and_the_readme_state_the_same_contract`
