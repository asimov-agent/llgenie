## ADDED Requirements

### Requirement: Untrusted Actions expressions reach shells only through env
In the four flagged shipped CI files (`.github/actions/agent-leg/action.yml`,
`.github/workflows/engine-build-pr-trigger.yml`, `.github/workflows/run-failure-reactor.yml`,
`.github/workflows/review-verdict.yml`), a `run:` step SHALL NOT interpolate a workflow
`inputs.*`, `github.event*`, or `steps.*.outputs` expression into the shell command text. Every
such value SHALL be declared in the step's `env:` and referenced as a shell variable.

#### Scenario: dispatch refs reach the git commands as env
- **Given** a `workflow_dispatch` of `engine-build-pr-trigger.yml` with an arbitrary `branch` input
- **When** the `make engine-build-pr-trigger` step builds its `git fetch` / `rev-parse` / `make` command lines
- **Then** the branch and base refs arrive via `DISPATCH_BRANCH` / `DISPATCH_BASE_REF` env and the shell expands only `"$VAR"` references

#### Scenario: a hostile summary value cannot execute
- **Given** a `run_id` (or `pr_number`, verdict, head) whose value contains shell metacharacters
- **When** the Report step writes the summary
- **Then** the value is echoed literally from the env variable and no substring is parsed as shell

### Requirement: The semgrep referee reports zero run-shell-injection findings on the four files
A semgrep run of the shipped ruleset at the fixed head SHALL report no
`github-actions.security.run-shell-injection` finding in the four files named above.

#### Scenario: the scan judges the fixed head
- **Given** the implementing PR head
- **When** `make security-scan TOOL=semgrep` (locally) or the CI security job scans `.github/`
- **Then** no `run-shell-injection` finding names those four files
