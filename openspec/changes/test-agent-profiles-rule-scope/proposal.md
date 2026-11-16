# Proposal: test-agent-profiles-rule-scope

<!-- openspec-template: fill every section; do not delete markers. -->

## Why
`tests/test_agent_profiles.py::test_the_report_names_duplicate_canonical_rules_and_the_gate_does_not_fail_on_them`
reds a host whose pytest tmp base embeds a deduped lane name (issue #2330). The final assertion
checks `lane not in dup_report` as a substring of the WHOLE report, but `guard.report()` prints the
absolute agents-root path in its header — on a host whose scratch path contains
`llgenie-issse-implementer`, the header itself contains the deduped lane name and the assertion
fires although the report names only the synthetic `lane` profile. Measured on this host
(`TMPDIR` under the implementer profile scratch): 1 failed; with `TMPDIR=/tmp/...`: green.
CI hides it because the container tmp base is `/tmp/pytest-of-<user>`. A green CI next to a red
host trains people to dismiss the test as flaky — the posture that hides real duplicate-detector
regressions.

## What Changes
- **MODIFIED** the test's leak-detection assertion: the deduped-lane presence check is scoped to
  the RULE-HOLDER lines of the report (the `  <name>: <title> stated more than once` entries),
  not a substring of the whole report text. The report header path can no longer manufacture a
  false red.
- **ADDED** a re-flag control inside the same test: a synthetic duplicate stated by a profile
  named EXACTLY like a deduped lane (`llgenie-tester`) is built and the report must NAME it as a
  rule holder — proving the scoped check still catches a genuine re-flag (issue #2330 AC-2).
- No production code changes: `check_agent_profiles.py` behaviour is untouched (issue #2330
  "Not covered": no file outside this test needs changing).

## Impact
- Spec: `agent-profiles` — duplicate-canonical-rule report assertion is host-independent
- Tests: `tests/test_agent_profiles.py` (one test node modified + control extended)
- Gates: `make test-unit` must be green on a lane-named tmp base AND a clean `/tmp` base
