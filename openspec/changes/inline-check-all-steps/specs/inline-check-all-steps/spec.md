# inline-check-all-steps

## ADDED Requirements

### Requirement: the inline-script check inspects every step of every workflow

`check_workflow_inline_scripts` MUST extract and scan **every** `run:` block in every workflow file,
not only the last one. A `run:` block MUST end at the first non-blank line indented at or below the
`run:` line itself; the extractor MUST NOT rely on "a line with no leading whitespace" to end a block,
because a workflow nests every line under `jobs:`/`<job>:`/`steps:` and such a line never occurs.

#### Scenario: a violation in a step that is not the last one is a finding

- **Given** a workflow whose first step runs `python3 scripts/engine_skill_gap.py` and whose last step
  runs `make test-unit`
- **When** `check_workflow_inline_scripts` runs over it
- **Then** the first step's script call is reported, naming the step it is in
- **Test:** `tests/test_code_review.py::test_a_violation_in_a_step_that_is_not_last_is_still_a_finding`

### Requirement: the scan reads a step's commands, not its prose

A repo-script name inside a plain quoted string in a `run:` block MUST NOT be reported: it is a message,
not a command. A repo-script name inside a command substitution (`$( ... )`) or backtick MUST be
reported, because that IS a command.

#### Scenario: a script name quoted in a commit message is not a finding

- **Given** a step whose `run:` block writes `... (scripts/fix_loop.sh): the check ran ...` into a
  multi-line `git commit -am "…"` message
- **When** the check runs over it
- **Then** nothing is reported
- **Test:** `tests/test_code_review.py::test_a_script_name_in_a_quoted_message_is_prose_not_a_command`

#### Scenario: a script run in a substitution is still a finding

- **Given** a step whose `run:` block runs the script in `gap="$(python3 scripts/engine_skill_gap.py …)"`
- **When** the check runs over it
- **Then** it is reported
- **Test:** `tests/test_code_review.py::test_a_script_in_a_substitution_is_still_a_command`
