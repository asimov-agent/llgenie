# agent-own-worktree

## ADDED Requirements

### Requirement: each agent uses its own worktree
Every agent MUST do its work in its own git worktree at `../llgenie-wt/<kebab>`,
created from the latest `origin/main`. The user's checkout MUST stay on the
branch the user left there. A second agent MUST use a second worktree.

WHEN an agent starts or resumes a feature branch,
THEN it works in `../llgenie-wt/<kebab>` and does not `git switch` that branch
in the user's checkout.

#### Scenario: a new branch is cut in a new worktree
- **Given** the latest `origin/main`
- **When** an agent starts `feat/<kebab>`
- **Then** `AGENTS.md` tells it to run `git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main`
- **And** `AGENTS.md` does not contain `NO git worktrees`
- **Test:** `tests/test_agents_worktree.py::test_each_agent_works_in_its_own_worktree`
