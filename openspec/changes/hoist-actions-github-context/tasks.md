# Tasks

- [x] 1. `.github/workflows/engine-build-pr-trigger.yml` `run:` dispatcher interpolates NO `${{ github.* }}` context directly into the shell — the base sha and head ref ride through step-level `env:` (`PR_BASE_SHA`, `PR_HEAD_REF`) and are referenced as `"$PR_BASE_SHA"` / `"$PR_HEAD_REF"` in the make invocation
- [x] 2. `containers.scanners.semgrep.rules.yaml.github-actions.security.run-shell-injection.run-shell-injection` no longer fires against `.github/workflows/engine-build-pr-trigger.yml` at the fixing head — reproduced pre-fix (1 match at `31 findings`), proven post-fix (`0` run-shell-injection of `30`) on the same pinned image `ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609` + rules `35377b8f`
- [x] 3. The workflow YAML still parses and the make step's `env` is `GH_TOKEN, PR_BASE_SHA, PR_HEAD_REF` with the `run:` block clean of `${{ }}` github context
