# 2026-11-16 — test(agent-profiles): rule-scoped leak check (issue #2330)

Issue: #2330 · OpenSpec: `test-agent-profiles-rule-scope` · Branch: `feat/2330-agent-profiles-rule-scope`

## What was verified
- Reproduced the false red on the pre-fix tree: `TMPDIR` under
  `~/.hermes/cache/scratch/llgenie-issse-implementer-base` →
  `test_the_report_names_duplicate_canonical_rules_and_the_gate_does_not_fail_on_them`
  failed at the substring assertion (`for lane in deduped: assert lane not in dup_report`)
  because `guard.report()` prints the absolute agents-root path in its header.
- Fix (test-only, per the issue's "Not covered"): the presence check is now scoped to
  rule-holder lines (`  <name>: <title> stated more than once`), matching the shape the
  first half of the test already parsed. Added an AC-2 control: a synthetic profile named
  exactly `llgenie-tester` stating the canonical block twice must be NAMED as a rule holder —
  the scoped check keeps its bite against a genuine re-flag.
- Proved both bases post-fix: lane-named `TMPDIR` → 150 passed rc=0; `TMPDIR=/tmp/ptest-clean`
  → 150 passed rc=0. Full `make test-unit` run tracked separately.

## Decision
No production change: `check_agent_profiles.py` already separates header path lines from
duplicate-rule lines; only the test conflated them.

## Status
Module green on the hostile base and the clean base; full unit gate + PR follow.
