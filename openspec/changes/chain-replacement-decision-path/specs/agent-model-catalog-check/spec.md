## ADDED Requirements

### Requirement: The drift issue names its own replacement decision path

The drift issue body rendered by `scripts/check_agent_model_catalog.py` SHALL state the decision
path for every retired chain member: name one replacement candidate, record the choice on the
drift issue, implement the re-pin as its own issue→branch→OpenSpec→PR lane whose PR closes the
drift issue, and re-verify with `make check-agent-model-catalog` after the replacement lands.
The check itself SHALL NOT edit the chain config; it only files and updates the drift issue.

#### Scenario: dry-run body carries the decision path

- **WHEN** `python3 scripts/check_agent_model_catalog.py --catalog <fixture> --dry-run` runs
  against a catalog fixture missing a declared chain member
- **THEN** the rendered body's `How we fix it` section names the four decision-path steps:
  naming one candidate, recording the choice, the closing PR lane, and the post-landing
  `make check-agent-model-catalog` verification

#### Scenario: every named member gets a drop-in candidate list with budgets

- **WHEN** the drift issue is rendered for a member whose committed `context_window` is B
- **THEN** the body lists, for that member, every `:free` catalog id whose published
  `context_length` >= B (or states that no drop-in exists), so the replacement is provably a
  budget-preserving drop-in from the issue body alone

#### Scenario: the alarm semantics stay unchanged

- **WHEN** a member is missing or a budget drifts
- **THEN** `compare()` still prints exactly the #2930 FINDING lines and the process still
  exits 1, files one marker-deduped issue, and never edits any config file
