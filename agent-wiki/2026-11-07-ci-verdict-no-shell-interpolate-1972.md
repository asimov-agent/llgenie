# ci-verdict: carry the dispatch head_sha via env, not shell interpolation (#1972)

Semgrep's `yaml.github-actions.security.run-shell-injection` rule (severity high, component:code)
flagged `.github/workflows/ci-verdict.yml:159`: the `judge` job's "Read the finished run" step
interpolated `${{ inputs.head_sha }}` directly inside its `run:` shell block. GitHub expands `${{ }}`
expressions **before** the shell runs, so a crafted `head_sha` value could break out of the quoted
assignment and inject shell commands into a job that holds `checks: write`. The workflow's own later
step already followed the safe pattern (`HEAD_SHA` env var + quoted `$HEAD_SHA`), so the flagged step
was the outlier.

Fix: the "Read the finished run" step now carries the optional dispatch input through its `env:` block
(`HEAD_SHA: ${{ inputs.head_sha }}`) and references `"$HEAD_SHA"` in the script — no `${{ }}`
expression remains inside any `run:` shell. Behaviour is unchanged: on the `workflow_run` path
`inputs.head_sha` is empty and the `else` branch resolves the run's own head; on a dispatch the
operator-supplied head is written as before.

Guard-prove on the repo's pinned semgrep image (`ghcr.io/asimov-agent/llgenie/semgrep:69170b46efd8`,
`--config=p/default`): the pre-fix file still reports the `check_id` at line 159, and the fixed head
reports **0** matches — a real source fix, not a suppression. No `# nosemgrep:` carve, no
`data/security-policy.json` change, no rule widening. Fix PR closes #1972.
