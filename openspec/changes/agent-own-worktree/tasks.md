# agent-own-worktree — Tasks

Issue: [#216](https://github.com/asimov-agent/llgenie/issues/216)

- [x] 1. `AGENTS.md` requires one worktree per agent at `../llgenie-wt/<kebab>` and forbids editing the user's checkout.
- [x] 2. `tests/test_agents_worktree.py::test_each_agent_works_in_its_own_worktree` locks that text and is in `make test-unit`.
- [x] 3. `make openspec-validate NAME=agent-own-worktree` exits 0.
