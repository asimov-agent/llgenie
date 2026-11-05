# Acceptance-criteria form contract — fleet rollout, pr-merge-conflict lane

## ADDED Requirements

### Requirement: form contract stated verbatim in the lane skill

The `llgenie-pr-merge-conflict` lane's `SKILL.md` under `agents/` states the
acceptance-criteria form contract verbatim.

#### Scenario: lane files an issue

Given the `llgenie-pr-merge-conflict` lane is filing any issue
When the issue body is composed
Then it carries a `## Acceptance criteria` markdown section
And each criterion is a `- [ ]` checkbox, one per provable outcome
And a criterion a reviewer cannot tick is not a criterion (#745)

#### Scenario: lane opens a PR body

Given the `llgenie-pr-merge-conflict` lane is opening a PR
When the PR body is composed
Then it carries a `## Acceptance criteria` markdown section
And each criterion is a `- [ ]` checkbox, one per provable outcome

### Requirement: text-only change under the lane dir

The change stays text-only under `agents/llgenie-pr-merge-conflict/`.

#### Scenario: change is docs-only

Given the change is the form-contract skill text plus its change-note pair
Then no scripts, tests or workflows are altered
And the PR diff is text-only.
