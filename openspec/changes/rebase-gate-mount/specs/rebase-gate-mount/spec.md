# rebase-gate-mount

## ADDED Requirements

### Requirement: The structural gate mounts the checkout

The rebase bot's structural gate SHALL mount the checkout as a path even when the job has exported
`REPO` as the repository slug. The sweep SHALL still receive the slug. The invariant SHALL hold on
every host: the mount (`TEST_OPTS`) SHALL name the checkout path, never the slug, and the recipe a
host expands SHALL carry the shape that host runs — the test image and its volume on a container
host, the native 3.11 venv command with no volume on macOS (the `HOST_OS` branch of the `Makefile`).

WHEN make lint is expanded with REPO set to asimov-agent/llgenie
THEN the volume source is the checkout and the slug is not a mount,
AND  on macOS the recipe is the native venv command, carrying no volume at all.

#### Scenario: a slug in the environment does not become the volume

Given the bot job has exported REPO as the slug
When  the mount (TEST_OPTS) and the lint recipe are expanded
Then  the volume source is the checkout path and the slug is not mounted.

- **Test:** `tests/test_rebase_bot_gates.py::test_the_lint_gate_mounts_the_checkout_when_repo_is_the_slug`

#### Scenario: a host that runs the gate natively still carries no slug

Given a Darwin host, where the lint recipe runs in the 3.11 venv instead of the test image
When  the lint recipe is expanded with REPO set to the slug
Then  it expands to the native venv command, with no volume source and no test image.

- **Test:** the `CONTAINER_HOST is False` branch of
  `tests/test_rebase_bot_gates.py::test_the_lint_gate_mounts_the_checkout_when_repo_is_the_slug`,
  exercised for real by CI job `macos / unit` -> `make ci-unit`

#### Scenario: the sweep still receives the slug

Given the same exported slug
When the sweep recipe is expanded
Then it is invoked with --repo set to that slug.

- **Test:** `tests/test_rebase_bot_gates.py::test_the_sweep_still_receives_the_slug`
