# agent-shell-credentials — spec delta

Capability: `agent-shell-credentials`
Issue: [#3020](https://github.com/asimov-agent/llgenie/issues/3020)

## MODIFIED Requirements

### Requirement: The check finds the Hermes install its own user can read

The credential check SHALL discover the Hermes install root by testing each candidate
(`<HERMES_AGENT_ROOT>`, `/root/.hermes/hermes-agent`, `~/.hermes/hermes-agent`) through a probe that
treats an UNREADABLE candidate as absent: a probe that raises `PermissionError` (an ancestor the
container user cannot traverse, e.g. `/root` at mode `0700`) SHALL be skipped and discovery SHALL
continue with the next candidate. The root that was chosen, and any candidate skipped as unreadable,
SHALL be printed. The check SHALL still exit non-zero with a named reason when no candidate is
readable, and no credential VALUE shall be read or printed on any path.

WHEN the check runs in a container whose user cannot traverse `/root`,
THEN it SHALL fall through to the Hermes install that user can read and run its Hermes terminal probe
against it, rather than ending the preflight with a permission error.

#### Scenario: an unreadable candidate is skipped, not fatal
Given candidate roots where the first raises `PermissionError` on its probe path and a later candidate
is a readable Hermes install,
When   the check resolves the Hermes install root,
Then   it returns the readable install, reports the candidate it skipped as unreadable, and the check
       proceeds to its probe.
- **Test:** `tests/test_agent_shell_keys.py::test_the_default_discovery_skips_the_unreadable_candidate`

#### Scenario: no readable candidate stays a loud failure
Given only unreadable or missing candidates,
When   the check resolves the Hermes install root,
Then   it raises with a reason that names the candidates it looked at and which were unreadable.
- **Test:** `tests/test_agent_shell_keys.py::test_no_readable_candidate_is_still_a_loud_failure`

#### Scenario: the readable candidate still wins when it is the only one
Given exactly one readable Hermes install candidate,
When   the check resolves the Hermes install root,
Then   that candidate is returned and nothing is reported as skipped.
- **Test:** `tests/test_agent_shell_keys.py::test_the_only_readable_candidate_is_the_one_chosen`
