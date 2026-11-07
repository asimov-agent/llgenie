# ci-verdict-no-shell-interpolate

## MODIFIED Requirements

### Requirement: the judge's shell steps must not interpolate GitHub context expressions

The `judge` job's steps MUST NOT place `${{ ... }}` context expressions inside a `run:` shell
block, because GitHub expands them before the shell runs and an untrusted input value (such as
`inputs.head_sha` on a `workflow_dispatch`) could then inject shell commands into a job holding
`checks: write`. Context values that a `run:` step needs MUST be carried in the step's `env:` block
and referenced as quoted shell variables instead.

WHEN the judge job's "Read the finished run" step runs
THEN the optional dispatch head sha is read from a `$HEAD_SHA` environment variable (set from
`inputs.head_sha`), never from an interpolated `${{ inputs.head_sha }}` inside the shell

#### Scenario: a dispatch re-judge writes the operator-supplied head sha via an env var

- **Given** a `workflow_dispatch` re-judge of ci-verdict.yml with `inputs.head_sha` set
- **When** the "Read the finished run" step runs
- **Then** the step reads the value as `"$HEAD_SHA"` (its `env:` block maps `HEAD_SHA` to
  `inputs.head_sha`), writes it to `$RUNNER_TEMP/verdict/head_sha`, and its `run:` block contains no
  `${{ }}` expression

#### Scenario: the workflow_run auto path is unchanged

- **Given** a completed `CI` run judged by the `workflow_run` trigger (no dispatch inputs)
- **When** the "Read the finished run" step runs
- **Then** `inputs.head_sha` is empty, the `else` branch resolves `HEAD_SHA` from the run's own
  `head_sha` via `gh api`, and the verdict is judged and posted exactly as before

### Requirement: the fix must not weaken the shell-injection rule guard

Fixing the source must not suppress the rule: no inline `# nosemgrep:` carve, no
`data/security-policy.json` change, and no widened severity/allowlist set. The only acceptable
close is the flagged `${{ inputs.head_sha }}` no longer appearing in any `run:` shell block of
`.github/workflows/ci-verdict.yml`, proven by a clean run of the repo's own pinned semgrep image on
the fixed file with a pre-fix control that still matches.

WHEN the fixed workflow is scanned with the repo's pinned semgrep image
THEN the reported `check_id` has 0 matches on the fixed head, while the same scan on the pre-fix file
reports the rule at the flagged region

#### Scenario: the guard-prove pair on the pinned semgrep image

- **Given** the repo's pinned semgrep image and a checkout of the fixed workflow
- **When** `scan --config=p/default --json --metrics off` runs against the fixed file and against the
  pre-fix file
- **Then** the fixed head reports `0` results for the `check_id`, and the pre-fix file still reports
  the rule at the flagged region — proving the close is a real source fix, not a suppression

