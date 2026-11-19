# Change: chain-replacement-decision-path

## Why

Issue #2939: the weekly catalog check (#2930, PR #2940) files a drift issue whenever a Hermes
chain member leaves the live Nous catalog — but a retired member must end with a LANDED
replacement, not a repeat alarm. Today the drift issue lists `:free` candidates yet never names
the decision path: who picks a candidate, how the replacement is implemented (issue → branch →
OpenSpec → PR that closes the drift issue), and what proves the replacement is a drop-in
(published budget >= the retired member's committed context_window).

## What Changes

- `scripts/check_agent_model_catalog.py::issue_text`: the drift-issue `how` becomes an explicit
  decision path: (1) name ONE replacement candidate from the drop-in list and record the choice
  on the drift issue, (2) implement the re-pin as its own issue→branch→OpenSpec→PR lane whose
  PR closes THIS drift issue (one landed replacement, no repeat-alarm cycle), (3) the weekly
  check re-verifies the new pin (rc=0) and the image check proves the chain installed.
- Candidate enumeration gains budgets: for every named member the drift issue lists `:free`
  drop-in candidates whose published `context_length` >= that member's committed budget, so a
  drop-in replacement is provable from the issue body alone (AC2 of #2939).
- `compare()` keeps its alarm lines; the drop-in computation happens at render time so the
  alarm semantics (#2930) are unchanged.
- Tests in `tests/test_check_agent_model_catalog.py` assert the dry-run body carries the decision
  path steps and per-member drop-in candidates for a synthetic retired member.
