# ci-verdict own-workflow and cancelled-auto-merge rows

## MODIFIED Requirements

### Requirement: A blocking check-run is an unjudged red only when it is a real external red

`unjudged_reds` names the head's blocking check-runs that belong to a workflow the verdict did not
judge, so a plain `success` is never posted beside a red `auto_merge.py` would refuse (#2116). Two
creator classes are NOT external reds and MUST be excluded:

- rows whose workflow FILE is the verdict's OWN `.github/workflows/ci-verdict.yml` — a `workflow_run`
  workflow auto-creates a per-job check-run on the head it runs on (the default branch), named after
  the job key, so the verdict's own `judge`/`guard` rows sit on a main head and a previous red leaves
  them `failure`; counting them re-counts the verdict into its own red (measured run `42461521651` at
  `07a7db2a`);
- an auto-merge row whose conclusion is `cancelled` — auto-merge cancels its own superseded sweeps
  repo-wide (`cancel-in-progress: true`, #917), so a cancelled `merge` row is churn, not a defect
  (measured run `42461420528`).

The exclusion is by workflow FILE (the stable identity `workflow_of` resolves), never by the
`ci-verdict` check NAME alone, because the auto job row is named `judge`/`guard`, not `ci-verdict`.

#### Scenario: the verdict's own judge rows are not unjudged reds

Given a green judged run and a head whose check-runs include blocking rows whose workflow FILE is
`.github/workflows/ci-verdict.yml` (a prior verdict run's `judge` job rows, `conclusion=failure`),
when `unjudged_reds` runs,
then those rows are NOT returned and the verdict posts `success`.

#### Scenario: a cancelled auto-merge merge row is not an unjudged red

Given a green judged run and a head whose check-runs include an auto-merge `merge` row with
`conclusion=cancelled`,
when `unjudged_reds` runs,
then that row is NOT returned and the verdict posts `success`.

#### Scenario: a real auto-merge merge failure is still an unjudged red

Given a green judged run and a head whose check-runs include an auto-merge `merge` row with
`conclusion=failure`,
when `unjudged_reds` runs,
then that row IS returned and the verdict posts `failure` (the gate is not weakened).

### Requirement: The posted check-run title says what the posted conclusion says

The `output.title` of the check-run the verdict posts is derived from the POSTED conclusion, never
from the judged verdict word alone: the title reads `ci-verdict: green` ONLY when the posted
conclusion is `success`. A failed or superseded head is never titled `green`.

#### Scenario: a failed verdict is not titled green

Given a green judged run whose head still carries a genuine unjudged red (so the posted conclusion is
`failure`),
when the check-run payload is written,
then `payload["output"]["title"]` does NOT contain `green` and `payload["conclusion"]` is `failure`.
