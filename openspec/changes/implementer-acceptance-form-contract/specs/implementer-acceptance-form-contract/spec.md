# implementer-acceptance-form-contract

## ADDED Requirements

### Requirement: the implementer lane carries the acceptance-criteria form contract in its versioned active skill

`agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/SKILL.md` (folded
live→tree via #1060) SHALL state the form contract verbatim from #1796 #1: every issue this lane files
AND every PR body it opens has a `## Acceptance criteria` section with each criterion a `- [ ] `
markdown checkbox — one per provable outcome; a criterion a reviewer cannot tick is not one (#745). The
section SHALL use the canonical `## ` heading, never a bare `**Acceptance criteria:**` bold heading
(which defeats `issue_body.missing()` and the verdict-gated ticking in `acceptance_writeback`, #1644).
The contract SHALL be versioned via #791 (issue → PR under `agents/llgenie-issse-implementer/`,
text-only) and announced with the #1724 SYNC bullet
`make sync-agent-profile PROFILE=llgenie-issse-implementer`.

#### Scenario: the active skill names the contract and the canonical-`##`-heading constraint

- **Given** `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/SKILL.md`
- **When** the acceptance-criteria form-contract section is read
- **Then** it states that every filed issue and every opened PR body carries a `## Acceptance criteria`
  `- [ ]` checkbox list, one checkbox per provable outcome, and it names the #745 caveat and the
  canonical-`## `-heading requirement

#### Scenario: the contract is versioned and announced, not privately edited

- **Given** the contract change in this PR under `agents/llgenie-issse-implementer/`
- **When** the change is committed and the PR is opened
- **Then** the PR body carries `closes #1812` and the `SYNC: llgenie-issse-implementer
  make sync-agent-profile PROFILE=llgenie-issse-implementer` line (#1724), and the PR's own diff adds the
  `openspec/changes/implementer-acceptance-form-contract/` change (satisfying the #1807 presence gate)

#### Scenario: no gate code is altered

- **Given** the implementer-lane roll-out
- **When** the PR's diff is listed
- **Then** `scripts/issue_body.py`, `scripts/acceptance_writeback.py` and `.github/workflows/auto-merge.yml`
  are unchanged (#1644/#1088/#491 intact), and no peer-lane `agents/*` file is edited
