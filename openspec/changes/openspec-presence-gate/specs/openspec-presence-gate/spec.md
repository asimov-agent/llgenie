# openspec-presence-gate

## ADDED Requirements

### Requirement: an implementing PR's diff adds an OpenSpec change, or the body names one, or the PR is docs-only

When a bot intended PR's range is checked, the range SHALL add at least one file under
`openspec/changes/<name>/`, or the PR body SHALL name (via a `OPENSPEC: <name>` line) an exact,
currently-ACTIVE change the PR implements against, or every file the range touches SHALL be a pure
docs/regen file (under `docs/`, `agent-wiki/`, `CHANGES.md`, `README.md`, or the change-note trio).
Otherwise the gate SHALL refuse the PR with a finding naming the missing OpenSpec change and the
`make openspec-new` remedy.

WHEN a bot implementing PR's final diff adds no `openspec/` file, names no existing change, and is not
pure docs
THEN the gate exits non-zero and names the missing OpenSpec change directive.

#### Scenario: an openspec-empty implementing PR is refused

Given a bot PR whose range changes `scripts/...` and `tests/...` but adds no file under `openspec/`
and carries no `OPENSPEC:` line
When  the openspec-change gate runs
Then  it returns a finding naming the missing OpenSpec change and the `make openspec-new` remedy.

- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_an_openspec_empty_implementing_pr_is_refused`

#### Scenario: a PR whose diff adds its own OpenSpec change passes

Given a bot PR whose range adds `openspec/changes/<name>/` files
When  the openspec-change gate runs
Then  it returns no finding (structure and ticks are the existing `openspec-validate-all` /
      `openspec-tasks-check` job's verdict).

- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_a_pr_that_adds_its_own_change_passes`

#### Scenario: a body-named existing change exempts the PR

Given a bot PR whose range adds no `openspec/` file, whose body carries `OPENSPEC: <active-change>`
When  the openspec-change gate runs
Then  it returns no finding (the body deliberately names the change it implements against).

- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_a_body_named_existing_change_exempts`

#### Scenario: a pure docs/regen PR is exempt without naming a change

Given a bot PR whose range touches only `docs/`, `agent-wiki/`, `CHANGES.md` or the change-note trio
When  the openspec-change gate runs
Then  it returns no finding (there is nothing to spec-track).

- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_a_pure_docs_pr_is_exempt`

#### Scenario: a human-only range is skipped, never failed

Given a PR whose range carries no bot-authored commit
When  the openspec-change gate runs
Then  it returns no finding (a human leg is not held to the bot automation rule).

- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_a_human_only_range_is_skipped`

#### Scenario: the gate is wired into both guard docs and full CI

Given the two guard workflows
When  `make check-pr-openspec-change` runs on a PR
Then  both `ci.yml` and `scope.yml` carry the step with the live-body read, and the Makefile target /
      `.PHONY` / `docs/BOTS.md` row / change-note trio are all present.

- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_the_openspec_gate_is_wired_into_both_guard_docs_and_full_ci`

