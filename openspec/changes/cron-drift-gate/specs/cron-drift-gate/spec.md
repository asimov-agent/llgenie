## ADDED Requirements

### Requirement: a live planner cron prompt cannot drift from its versioned copy unnoticed

`make check-cron-drift` SHALL compare the live prompt of each planner cron in `CRON_JOBS` against its
committed copy under `agents/llgenie-planner/prompts/` and SHALL fail (exit 1) when any differs, naming
the drifted job and both byte counts.

#### Scenario: the committed copy matches live

- **GIVEN** a live jobs.json whose auto-approve-merge and auto-rebase-resolve prompts equal their
  versioned files
- **WHEN** `make check-cron-drift` runs
- **THEN** it exits 0 and prints `OK` for both jobs
- **Test:** `tests/test_check_cron_drift.py::test_gate_greens_when_both_live_prompts_match`

#### Scenario: one committed copy has diverged

- **GIVEN** a live jobs.json where one job's prompt differs from its versioned file
- **WHEN** `make check-cron-drift` runs
- **THEN** it exits 1, names the drifted job, and prints both byte counts; the intact job still
  reports `OK`
- **Test:** `tests/test_check_cron_drift.py::test_gate_reds_when_one_prompt_diverges`

### Requirement: a missing live file, job, or versioned copy is a failure, never a pass

If the live jobs.json, a checked job, or a versioned file is missing or unreadable, the gate SHALL
exit 2 rather than silently report agreement.

#### Scenario: versioned copy missing

- **GIVEN** no committed copy under `agents/llgenie-planner/prompts/`
- **WHEN** the gate runs
- **THEN** it exits 2 and prints the missing path
- **Test:** `tests/test_check_cron_drift.py::test_gate_exits_2_when_versioned_missing`
