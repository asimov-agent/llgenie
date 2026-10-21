# bot-implement-in-place

## ADDED Requirements

### Requirement: The implementer edits the mounted tree in place

The `implement-issue` leg runs Hermes in a `--rm` container with one writable mount at `/repo`. Its
prompt SHALL state that contract: the agent edits `/repo` in place, and SHALL NOT create a git worktree,
because a worktree path (`../llgenie-wt/...`) resolves outside the mount and is destroyed with the
container.

WHEN the implementer's prompt and its container invocation are read
THEN the prompt SHALL name `/repo` as the tree it edits in place and forbid a git worktree, and the
recipe SHALL mount exactly one writable tree at `/repo` (working directory `/repo`).

#### Scenario: the prompt forbids a worktree and names the in-place tree

Given the `_implement-issue` recipe
When  its prompt is read
Then  it says the agent runs inside the container, that `/repo` is the only writable checkout and the
      tree the job commits, and that it must not create a git worktree.

- **Test:** `tests/test_bot_in_place.py::test_the_prompt_forbids_a_worktree_and_names_the_in_place_tree`

#### Scenario: the leg mounts one writable tree

Given the `implement-issue` target
When  its container invocation is parsed
Then  there is exactly one `-v …,:/repo` mount and `-w /repo`, so a worktree path cannot resolve inside
      a second mount by accident.

- **Test:** `tests/test_bot_in_place.py::test_the_leg_mounts_one_writable_tree`

#### Scenario: the job, not the agent, commits and pushes

Given the same recipe
When  its hard rules are read
Then  pushing, merging and committing remain forbidden for the agent — the job owns the branch — so the
      in-place edit is the whole of the agent's task.

- **Test:** `tests/test_bot_in_place.py::test_the_agent_still_does_not_commit_or_push`
