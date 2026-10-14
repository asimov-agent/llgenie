# trending-registry

## ADDED Requirements

### Requirement: The vendored registry is additive only

The vendored `data/models.json` MUST never lose data against the previously
committed copy: no model, no key, no measurement group, no t/s and no
engagement counter may be removed or shrunk by a sync. Additions are always
allowed. A loss MUST fail `make check-registry` (CI unit job), and MUST NOT be
worked around by editing the vendored file locally — the loss belongs to
upstream, where the store is written.

WHEN `make sync-registry` replaces `data/models.json` with the upstream copy,
THEN `make check-registry` fails if anything the committed copy had is gone, and
the sync PR stays red until upstream restores it.

#### Scenario: a sync that only adds data passes the guard

- **Given** the committed registry and an upstream copy that added a key, a measurement, a backend or a raised counter
- **When** `make check-registry-keys` compares them
- **Then** it exits 0 and prints `OK: additive only`
- **Test:** `tests/test_registry_keys.py::test_compare_reports_every_kind_of_loss` (the "grown" case), `tests/test_registry_keys.py::test_cli_fails_a_lossy_sync_and_passes_an_additive_one`

#### Scenario: a sync that drops a key is caught

- **Given** a copy where a key present in the committed registry (e.g. `engagement.seen_posts`) is gone from every row of the model
- **When** `make check-registry-keys` compares them
- **Then** it exits non-zero and names `engagement.seen_posts` as gone
- **And** a key that survives on ONE measurement row of several is NOT reported (the list is compared as a key union)
- **Test:** `tests/test_registry_keys.py::test_compare_reports_every_kind_of_loss`, `tests/test_registry_keys.py::test_cli_fails_a_lossy_sync_and_passes_an_additive_one`

#### Scenario: a sync that loses a model, a measurement, a t/s or a counter is caught

- **Given** a copy that dropped a model, dropped every row of an `(engine, hardware)` measurement group, lowered a t/s, lowered a `likes`/`comments`/`reshares`/`views`/`interactions` counter, dropped a `backends` / `supported_engines` member, dropped a format, or removed an engine-registry entry
- **When** `make check-registry-keys` compares them
- **Then** each loss is reported with the model and field named, and the guard exits non-zero
- **Test:** `tests/test_registry_keys.py::test_compare_reports_every_kind_of_loss`

#### Scenario: the guard is green on the committed registry

- **Given** the real vendored `data/models.json`
- **When** it is compared against itself, and `make check-registry-keys` runs on a clean tree
- **Then** no loss is reported (no false positive on real data)
- **Test:** `tests/test_registry_keys.py::test_real_vendored_registry_is_additive_against_itself`, `tests/test_registry_keys.py::test_default_prev_is_a_git_revision_of_the_vendored_file`

#### Scenario: the guard is documented and wired

- **Given** the repo rulebook and the Makefile
- **When** the additive-only rule is looked up
- **Then** `AGENTS.md` states it and names `scripts/registry_keys.py`, `make check-registry-keys` is part of `check-registry`, and `make test-unit` runs the guard's tests
- **Test:** `tests/test_registry_keys.py::test_rules_and_wiring_are_documented`

#### Scenario: an unusable previous registry is an error, never a silent pass

- **Given** a previous copy that does not exist (a bad git revision or path)
- **When** the guard reads it
- **Then** it aborts with `cannot read previous registry`, not exit 0
- **Test:** `tests/test_registry_keys.py::test_unreadable_previous_revision_fails_loudly`

### Requirement: Agent-implemented issues end in a monitored, green, squashed PR

When an agent implements an issue it MUST work on a feature branch cut from the
tip of `main` with the OpenSpec change and tests in the same branch, MUST open
the PR (upstream base, fork head, `closes #<issue>`), MUST monitor the pipeline
that PR triggered and fix it until the checks are green, and MUST NOT merge a
red PR, a draft or a PR with unresolved review threads. The merge, where the
agent is the one merging, is a squash merge carrying a proper Conventional
Commit message so history stays one commit per change.

WHEN an agent finishes implementing an issue,
THEN the issue has an open PR whose checks the agent has driven green, and the
landed commit is a single Conventional Commit referencing the issue.

#### Scenario: the rule is stated in the rulebook

- **Given** the agent rulebook `AGENTS.md`
- **When** the agent-implemented-issues section is read
- **Then** it requires a feature-branch implementation, an opened PR, monitoring and fixing the PR's pipeline to green, and a squash merge with a proper commit message
- **Test:** `tests/test_registry_keys.py::test_rules_and_wiring_are_documented` (AGENTS.md contains both durable sections)
