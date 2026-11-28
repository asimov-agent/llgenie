# Bot outcome specification

## ADDED Requirements

### Requirement: a bot success marker requires a durable changed path
A bot outcome step SHALL call `scripts/check_bot_outcome.py verify-changed-path`
before writing any success/fixed marker. The helper SHALL exit non-zero when the
measured post-head equals the pre-head, no `agent/issue-<n>-*` branch on origin
matches the issue, and no PR names the issue. Empty PR/issue bodies and a triage
leg that never created a session are vacuous and SHALL count as no changed path.

#### Scenario: no-op ends non-success
- GIVEN a bot run with unchanged head, no matching issue branch and no PR
- WHEN the outcome guard runs
- THEN the helper exits non-zero and no `bot-done … fixed` marker is written

#### Scenario: vacuous check is never a change
- GIVEN a moved head but an empty PR body or no session created
- WHEN the outcome guard runs
- THEN the helper exits non-zero

### Requirement: all bot outcome steps inherit the guard
Every workflow whose outcome step writes a success/fixed marker SHALL carry the
guard step before that marker. Tests SHALL use a subset assertion (expected <=
actual workflow set), so a new bot inherits the guard without a test edit.

#### Scenario: real change passes
- GIVEN a moved head and a non-empty PR body naming the issue
- WHEN the outcome guard runs
- THEN the helper exits zero and the marker may be written

#### Scenario: a new bot inherits the guard
- GIVEN an additional workflow that writes a success marker
- WHEN its steps contain `make verify-bot-outcome` before that marker
- THEN the subset assertion stays green without editing the test
