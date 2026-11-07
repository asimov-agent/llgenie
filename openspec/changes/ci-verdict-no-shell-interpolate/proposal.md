# ci-verdict-no-shell-interpolate

## Why

Semgrep's `yaml.github-actions.security.run-shell-injection` rule (severity high, component:code)
flags `.github/workflows/ci-verdict.yml:159` because the `judge` job's "Read the finished run" step
interpolates `${{ inputs.head_sha }}` directly inside its `run:` shell block (lines 166-167). GitHub
expands `${{ }}` expressions **before** the shell runs, so a crafted `head_sha` value containing a
`"` (or other shell metacharacters) could break out of the quoted assignment and inject arbitrary
shell commands into a job that holds `checks: write`. The workflow's own later step (the `make
ci-verdict` step) already stores `${{ inputs.head_sha || ... }}` in an `env:` var and references the
shell variable — the safe pattern — so the flagged step is the outlier.

## What changes

Route the workflow expression through an environment variable in the "Read the finished run" step,
so no `${{ }}` context expression appears inside its `run:` shell. Add
`HEAD_SHA: ${{ inputs.head_sha }}` to the step's `env:` block and reference `"$HEAD_SHA"` in the
script in place of `"${{ inputs.head_sha }}"`. Behaviour is unchanged: on the `workflow_run` path
`inputs.head_sha` is empty and the `else` branch resolves the run's own head; on a
`workflow_dispatch` the operator-supplied head is written as before.

## Out of scope

- Any change to `scripts/ci_verdict.py` or to what the judge decides.
- The `${{ inputs.head_sha || ... }}` env expression in the later `make ci-verdict` step (line 185),
  which already follows the safe env-var pattern and is not flagged by the rule.
- Any other file or workflow — this finding is confined to `.github/workflows/ci-verdict.yml:159`.
