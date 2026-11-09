## ADDED Requirements

### Requirement: engines-selects-unit-security-battery

`scripts/ci_scope.py` SHALL select `linux/unit` for a diff whose classes include `engines` (i.e. any
`skills/engines/**` or `containers/engines/**` path), so the `check-engine-pins-published`,
`check-secret-output`, `check-proc-gate`, `check-security-scan` and `check-actions` gates run on an
engine-skill dependency-pin edit. The widening SHALL be read-only: a change that adds `engines` to the
`unit` stage must never remove a class, severity, allowlist entry or `fail_on` value.

#### Scenario: an engine skill pin edit runs the security battery

- **Given** a diff that changes `skills/engines/vllm/SKILL.md` (a generator of the engine-params pins)
- **When** `ci_scope.select()` runs on the `engines`-class set
- **Then** `linux/unit` is selected (`run`), allocating `check-engine-pins-published`,
  `check-secret-output`, `check-proc-gate`, `check-security-scan`, `check-actions`
- **Test:** `tests/test_ci_scope.py::test_an_engine_skill_pin_change_selects_the_unit_security_battery`

#### Scenario: a non-engine skill still selects unit via the skills class

- **Given** a diff that changes `agents/llgenie-planner/SKILL.md` (a `skills`-class path, no engine)
- **When** `ci_scope.select()` runs on the `skills`-class set
- **Then** `linux/unit` is still selected, from the `skills` class — proving `unit` gained `engines`,
  not that every class now runs it
- **Test:** `tests/test_ci_scope.py::test_an_engine_skill_pin_change_selects_the_unit_security_battery`

#### Scenario: a docs-only change still skips the unit battery

- **Given** a diff that changes `docs/ARCHITECTURE.md` (a `docs`-class path)
- **When** `ci_scope.select()` runs on the `docs`-class set
- **Then** `linux/unit` is NOT selected (the skip stays), proving the widening is scoped to `engines`
- **Test:** `tests/test_ci_scope.py::test_an_engine_skill_pin_change_selects_the_unit_security_battery`
