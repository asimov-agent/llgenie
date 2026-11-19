# Agent access policy — the acting identity, its scopes, and a gate over both

## ADDED Requirements

### Requirement: AGENTS.md names the acting identity and the required scope roster

`AGENTS.md` SHALL carry a section starting `## The agent's GitHub identity and required access` that
names the acting bot identity and every token scope the agent needs to work, each scope tied to the
step it unblocks. `make check-agent-access` reddens when the section is absent or missing a
required element (identity name, a scope token, or its operation mapping).

#### Scenario: the section is deleted

Given a repo tree whose `AGENTS.md` no longer carries the identity/access section
When `make check-agent-access` runs
Then the gate exits non-zero naming the missing section
And the full unit battery (`make test-unit`) reddens because it runs the gate

#### Scenario: a scope loses its operation

Given the section exists but no longer maps `delete:packages` to the GC step it authorizes
When `make check-agent-access` runs
Then the gate exits non-zero naming the missing scope mapping

### Requirement: the host-agent skill carries the audit and identity-check rules

`agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md` SHALL exist and state: the
scope→operation map, the rule that an elevated or destructive step runs only when an open issue
already requests it, the rule that every such run is stamped on the issue that requested it, and the
identity check via `gh auth status` (masked tokens only). The same gate reddens a removed skill or a
removed rule.

#### Scenario: the skill file is removed

Given a repo tree without `agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md`
When `make check-agent-access` runs
Then the gate exits non-zero naming the missing skill

#### Scenario: the audit rule is stripped from the skill

Given the skill exists but no longer names the per-issue stamp requirement
When `make check-agent-access` runs
Then the gate exits non-zero naming the missing rule phrase

### Requirement: the policy artifacts cannot carry a credential

The gate SHALL refuse any token-shaped string (`gh[pousr]_` followed by 20+ token characters, or
`github_pat_` followed by 20+ token characters) appearing inside the AGENTS.md policy section or
inside the skill file, so the artifacts that grant access provably contain no secret.

#### Scenario: a token value is pasted into the section while debugging

Given the AGENTS.md policy section contains a `gho_`-prefixed 36-character string
When `make check-agent-access` runs
Then the gate exits non-zero and reports only the kind of secret and its file location, never the value

### Requirement: the gate runs in the unit battery

`scripts/ci_unit.py` SHALL list `make check-agent-access` among its steps, so any PR that drops the
identity policy reddens the `ci-unit` job like the issue-body shape gate does.

#### Scenario: a PR deletes the gate's step

Given `scripts/ci_unit.py` no longer names `make check-agent-access`
When `tests/test_check_agent_access.py` runs
Then that test fails on the battery-step assertion
