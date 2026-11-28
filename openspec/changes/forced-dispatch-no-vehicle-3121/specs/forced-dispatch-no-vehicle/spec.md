## ADDED Requirements

### Requirement: lane skills resolve in the agent image
The image build SHALL register the mounted checkout's `.hermes/skills` directory in the global Hermes
home AND in every installed lane profile's config, and SHALL read each registration back.

#### Scenario: profile leg preloads issue-triage
- **Given** the agent image is built from this tree and the checkout is mounted at `/repo`
- **When** the leg runs `hermes -p llgenie-planner -s issue-triage`
- **Then** the `issue-triage` skill resolves from `/repo/.hermes/skills/issue-triage/SKILL.md`

### Requirement: no green run without a verdict or vehicle
The issue-bot workflow SHALL fail when the triage leg exits nonzero, when no verdict is reached, or
when an `implement` verdict has no changed tree, no pushed branch and no PR.

#### Scenario: triage leg dies on an unknown skill
- **Given** `make issue-bot-triage` exits nonzero
- **When** the outcome comment has been written
- **Then** the workflow exits nonzero and names the triage rc in an error annotation

#### Scenario: implement verdict opens no vehicle
- **Given** the verdict is `implement` and no PR URL was produced
- **When** the outcome guard runs
- **Then** the workflow exits nonzero and names `changed`, `pushed` and `pr` in an error annotation

### Requirement: blocked targets are refused
`dispatch` SHALL return `action=blocked` with a reason for a forced issue carrying `blocked`, without
writing a claim comment or an issue.md.

#### Scenario: forced dispatch onto a blocked issue
- **Given** the forced issue has the `blocked` label
- **When** `dispatch` is called with that issue number
- **Then** it returns `action=blocked` with reason `blocked-label`, and neither a claim comment nor issue.md is written
