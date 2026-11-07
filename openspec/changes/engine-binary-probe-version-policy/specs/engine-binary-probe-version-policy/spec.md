# engine-binary-probe-version-policy

## ADDED Requirements

### Requirement: a `binary_probe: version` cell answers its version family and needs no help flag

A CLI whose parser has NO help flag (its `-h`/`--help` are a separate subcommand, e.g.
tensorfold/cuda at the 1.2.1 pin, issue #1888) MAY be marked `binary_probe: version`. `decide()`
MUST then require the version family to answer (the binary self-proves) and MUST NOT fail the
cell for the help family the binary truthfully lacks.

WHEN a cell is marked `probe: version`
THEN its version family must answer — the binary self-proves, and the image's own `detect` re-answers it — and the help family is exempt because the binary truthfully has none

#### Scenario: a version-only CLI answers its version and skips the help family

- **Given** verdicts where `--version` answers (exit 0, non-empty) and every help spelling
  (`-h`, `--help`) exits 2 with no output
- **When** `decide(["--version"], verdicts, policy="version")` runs
- **Then** the verdict `ok` is True (the version self-proves; the empty help family is exempt),
  while the SAME verdicts under the default `flags` policy still fail naming the help family
- **Test:** `tests/test_engine_binary_flags.py::test_a_version_only_cli_is_not_failed_for_having_no_help_flag`

#### Scenario: a `version` cell is not an escape hatch

- **Given** a `probe: version` cell whose version family also answers nothing (all flags exit 2)
- **When** `decide()` runs with `policy="version"`
- **Then** the verdict `ok` is False — the version is NOT left to `detect`; the cell reds like any
  other policy
- **Test:** `tests/test_engine_binary_flags.py::test_a_version_only_cli_with_a_dead_version_flag_still_reds`

## CHANGED Requirements

### Requirement: probe policies are `flags`, `device`, `help` and `version`

The accepted `binary_probe` policy set in `scripts/engine_skills.py` is extended from
`("device", "help")` to `("device", "help", "version")`. `probe_policy()` accepts `version`; the
skill validation message names all four; and the committed `containers/engines/binaries.json`
carries `tensorfold/cuda` `probe: "version"` (regenerated from its skill).

WHEN a skill declares `binary_probe: {cuda: version}`
THEN the generated manifest records `probe: "version"` for that cell and validation accepts it

#### Scenario: the version policy is generated and validated

- **Given** a skill whose per-backend `binary_probe` marks cuda `version`
- **When** `make generate-engine-params` runs
- **Then** `containers/engines/binaries.json` carries `tensorfold/cuda` `probe: "version"`, and
  skill validation (`BINARY_PROBES`) accepts it
- **Test:** `tests/test_engine_skills.py::test_probe_policy_honours_the_version_only_per_backend_branch`
  (direct: reads the committed tensorfold skill, asserts `probe_policy(tf, "cuda") == "version"`,
  `metal == "flags"`, and that the generated manifest carries `probe: "version"`); plus
  `tests/test_engine_skills.py::test_each_ci_cell_is_in_the_committed_manifest` (the probe-set
  assertion now includes `version`)
