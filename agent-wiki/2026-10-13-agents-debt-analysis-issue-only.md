# 2026-10-13 analysis → issues, never implementation (issue #231)

Fixing the registry-sync gate (#223, merged as #224) surfaced four problems that
were *not* the fix: the engine-ranking rule (#225), the scope/filter question
(#227), the per-engine list + matrix coverage (#228), and the unskilled-engine
gap (#229). They were filed as separate issues and not folded into the PR.

## What changed

`AGENTS.md` gains a durable rule: **every change MUST be analysed for real gaps
and technical debt, and each demonstrable finding MUST be filed as its own
detailed issue — never implemented inside the current change, never left as
prose.** Analysis ships issues, not code. The change being shipped keeps its one
objective; the findings become separate, linked work items.

Enforcement mirrors #217 (agent-own-worktree):

- `tests/test_agents_debt_analysis.py` asserts the rule text is present in
  `AGENTS.md` (the section must still say findings are separate issues and must
  not be implemented in the same change).
- The test is wired into `make test-unit`, so removing the rule turns CI red.

## Why this shape

- Docs + test only: no product behaviour change. The rule is process, so the
  guard is a text assertion like #217's, not a behavioural test.
- The findings themselves are out of scope here by design — that is the rule's
  point. The first application (is the trending list accurate given how llgenie
  behaves; the `model_engine_pick.py` refactors) is filed as issues.

## Status

- OpenSpec change `agents-debt-analysis-issue-only` validates; tasks checked.
- `make lint` OK; the new test passes in `llgenie/test:latest`.
