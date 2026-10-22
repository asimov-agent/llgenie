# rebase-gate-mount

## ADDED Requirements

### Requirement: The structural gate mounts the checkout

The rebase bot's structural gate SHALL mount the checkout as a path even when the job has exported
`REPO` as the repository slug. The sweep SHALL still receive the slug.

WHEN make lint is expanded with REPO set to asimov-agent/llgenie
THEN the volume source is the checkout and the slug is not a mount.

#### Scenario: a slug in the environment does not become the volume

Given the bot job has exported REPO as the slug
When the lint recipe is expanded
Then the docker volume source is the checkout path.

- **Test:** `tests/test_rebase_bot_gates.py::test_the_lint_gate_mounts_the_checkout_when_repo_is_the_slug`

#### Scenario: the sweep still receives the slug

Given the same exported slug
When the sweep recipe is expanded
Then it is invoked with --repo set to that slug.

- **Test:** `tests/test_rebase_bot_gates.py::test_the_sweep_still_receives_the_slug`
