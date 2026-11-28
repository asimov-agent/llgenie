## ADDED Requirements

### Requirement: the long unit step emits bounded timestamped progress

The unit entry point MUST print a timestamped heartbeat to the job log at a bounded interval while its pytest child is still running. The heartbeat MUST include elapsed seconds, a human-readable duration, the child pid, and an explicit "progressing, not wedged" state. The child's stdio MUST be inherited and its exit code MUST be returned unchanged.

#### Scenario: pytest runs longer than one interval

- GIVEN the unit entry point with a one-second heartbeat interval
- WHEN the pytest child runs for three seconds
- THEN the job log contains three timestamped heartbeat lines with increasing elapsed durations
- AND the entry point returns the child's own exit code

### Requirement: the heartbeat does not replace the hang ceiling

The progress signal MUST NOT add, shorten, weaken or remove the 120-minute job timeout in `.github/workflows/pipeline.yml`.

#### Scenario: a monitoring check inspects the workflow

- GIVEN the patched workflow tree
- WHEN the job timeout declarations are read
- THEN both 120-minute ceilings are still present
- AND no workflow-level heartbeat switch has been introduced
