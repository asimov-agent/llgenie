# hoist-actions-github-context — proposal

Issue: [#2241](https://github.com/asimov-agent/llgenie/issues/2241)

## Why

Semgrep's `yaml.github-actions.security.run-shell-injection.run-shell-injection` (pinned pack
`35377b8f`, severity `high`) reds `.github/workflows/engine-build-pr-trigger.yml:84` because the
`run:` dispatcher interpolates `${{ github.event.pull_request.base.sha }}` and `${{ github.head_ref }}`
directly into the shell. Github context data can carry arbitrary user input and must be treated as
untrusted; interpolating it into a `run:` script is an OS-command-injection class the scan rightly
reports as `component:code`.

## What changes

The two github-context values ride through step-level `env:` (`PR_BASE_SHA`, `PR_HEAD_REF`) and are
referenced in the dispatcher as `"$PR_BASE_SHA"` / `"$PR_HEAD_REF"` — the exact mitigation the rule's
message documents. The make dispatcher still receives the base sha and the source branch; runtime
behaviour is unchanged.

## Verification

Reproduced at origin/main `8e4e564f` (pinned image `ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`,
rules `35377b8f`): 31 semgrep findings total incl. this run-shell-injection at
`engine-build-pr-trigger.yml:84`. Post-fix at `a1b6b37b`: 30 findings, 0 run-shell-injection.
