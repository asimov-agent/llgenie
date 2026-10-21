# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: every structural gate must pass before the branch is pushed

`scripts/rebase_bot.sh`'s default gate command MUST chain its checks with `&&` (`make -n ci-unit &&
make lint && make check-wiring`), so the status is the failure of ANY gate rather than only the
last one. `.github/workflows/rebase-bot.yml` MUST provide the test image `make lint` runs in
(`make test-image`) before the rebase step, so that gate can pass on a runner.

WHEN a gate fails on a rebased branch
THEN the actor exits non-zero, publishes nothing, and does not claim the checks passed.

#### Scenario: a failing gate blocks the push
- **Given** a rebase that applies cleanly and a gate command that fails
- **When** the actor runs
- **Then** it exits non-zero and the remote branch is unchanged
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_structural_gate_fails_closed`

#### Scenario: the chain is AND, and the workflow supplies the lint image
- **Given** the actor's script and the rebase workflow
- **When** both are read
- **Then** the default gates are joined with `&&`, and `make test-image` runs before the drain step
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_default_gate_chain_and_the_pull_it_needs`
