# security #2241 — hoist github context out of the engine-build-pr-trigger run step

## The finding

`containers.scanners.semgrep.rules.yaml.github-actions.security.run-shell-injection.run-shell-injection`
(severity `high`) fired at `.github/workflows/engine-build-pr-trigger.yml:84` — the release-trigger
`run:` dispatcher interpolated `${{ github.event.pull_request.base.sha }}` and `${{ github.head_ref }}`
directly into the shell script. Semgrep treats github context as attacker-influenceable input in a
`run:` step (OS-command-injection class, CWE-78).

## The fix

The two github-context values now ride through step-level `env:` (`PR_BASE_SHA`, `PR_HEAD_REF`) and are
referenced in the dispatcher as `"$PR_BASE_SHA"` / `"$PR_HEAD_REF"` — the mirror of the rule's own
documented mitigation (an intermediate `env:` variable, then use it in the script). The make dispatcher
still receives the base sha and the source branch; runtime behaviour is unchanged.

## Verification

Reproduced at origin/main `8e4e564f` with the digest-pinned image
`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609` (rules pack `35377b8f`): `31` semgrep findings
total, `1` run-shell-injection (the finding). Post-fix at `a1b6b37b` on the same pinned image: `30`
findings, `0` run-shell-injection. Workflow YAML validates; make-step `env` is
`GH_TOKEN, PR_BASE_SHA, PR_HEAD_REF`; the `run:` block carries no `${{ }}` github context.

## Reference

- Issue: #2241 (security, severity:high, component:code)
- PR: #2271 (`fix(workflows): hoist github context into env vars ... (closes #2241)`)
- Change: `openspec/changes/hoist-actions-github-context/`
