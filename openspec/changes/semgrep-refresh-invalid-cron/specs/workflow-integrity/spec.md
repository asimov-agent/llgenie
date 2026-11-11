## ADDED Requirements

### Requirement: Every schedule cron fits GitHub's cron grammar

The workflow-integrity gate (`make check-workflows`) SHALL reject any
`.github/workflows/*.yml` whose `schedule: - cron:` value GitHub's cron parser cannot accept:
five whitespace-separated fields (minute 0-59, hour 0-23, day-of-month 1-31, month 1-12,
day-of-week 0-7 or SUN..SAT); each field a comma-separated list of entries; each entry `*`, a
single value, or a `lo-hi` range, each optionally stepped with `/N`. The check SHALL be
stdlib-only, like the rest of the guard, and a rejected value SHALL name the file and the value.

#### Scenario: The shipped bad cron is a red

- **Given** a workflow whose schedule is `- cron: "1 6 * * 15"` — `15` in the day-of-week field,
  the exact value that made GitHub answer `422 invalid cron attribute` (issue #2472)
- **When** `check_workflows.py check` runs over that tree
- **Then** the run exits non-zero with a `workflow-cron` finding naming the file and the value

#### Scenario: GitHub's whole grammar is accepted

- **Given** fixture crons `1 6 15 * *`, `*/6`, `47 */6 * * *`, `3,33 * * * *`,
  `19 */2 * * 0,2,3,4,5,6`, `53 6 * * 1`, `1-5 * * * MON-FRI`
- **When** the cron rule validates them
- **Then** none is reported

#### Scenario: The repository's own crons pass the rule

- **Given** this repository's `.github/workflows/` as the tree
- **When** `make check-workflows` runs
- **Then** it is GREEN — every cron this repo ships parses under the same grammar GitHub uses

### Requirement: The semgrep rules-pack refresh fires on its monthly date

`semgrep-rules-refresh.yml` SHALL schedule `- cron: "17 6 15 * *"` (06:17 UTC on the 15th — the
intent its own comments state), and after the fix lands on `main` GitHub SHALL parse the file:
no event (`push` or `pull_request`) shall create a run of it at a fresh head, and
`workflow_dispatch` SHALL be accepted (not `422 invalid cron`).

#### Scenario: No ghost at a fresh PR head after the fix

- **Given** the fixed file merged to `main`
- **When** any new `pull_request` event lands at a head sha
- **Then** the set of runs at that `head_sha` contains zero runs of `semgrep-rules-refresh.yml`

#### Scenario: Dispatch no longer 422s

- **Given** the fixed file merged to `main`
- **When** `workflow_dispatch` is requested for the workflow
- **Then** GitHub accepts it (HTTP 202) instead of refusing with `invalid cron attribute`
