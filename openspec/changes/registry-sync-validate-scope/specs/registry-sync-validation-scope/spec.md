# registry-sync-validation-scope

## ADDED Requirements

### Requirement: the sync job validates the registry it just synced

The registry-sync workflow's validation step SHALL run `make skills-validate` with the SAME
`REGISTRY` and `UNSUPPORTED` scope `ci-unit` uses, never the Makefile default fixture.

#### Scenario: the sync job's scope matches ci-unit's

- **GIVEN** the registry-sync workflow's validation step and `ci-unit`'s own `skills-validate` line
  in the Makefile,
- **WHEN** both are read,
- **THEN** the step pins `REGISTRY=data/models.json` and `UNSUPPORTED=data/unsupported-engines.json`,
  exactly like `ci-unit`.

- **Test:** `tests/test_registry_sync_trend.py::test_the_sync_job_validates_the_registry_it_just_synced`

#### Scenario: a recorded unsupported engine does not fail the gate

- **GIVEN** the registry as shipped on `main` (which contains engines recorded in
  `data/unsupported-engines.json`),
- **WHEN** the validator runs with that decisions file,
- **THEN** it reports 0 errors, where the same call without `--unsupported` errors on them.

- **Test:** `tests/test_registry_sync_trend.py::test_skills_validate_cli_with_the_decisions_exits_zero_on_the_october_5_fixture`
