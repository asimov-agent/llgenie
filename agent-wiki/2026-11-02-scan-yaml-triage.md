# 2026-11-02 — daily security-scan yaml triage: real least-privilege defects vs a false-positive class

## Measured

Daily security-scan run **41458285599** (`workflow_dispatch`, mode=full, scanned sha `febd964613b8`)
red at job `scan` with 14 findings carrying a fix. Semgrep SARIF downloaded from the run's own
`security-reports` artifact; yaml findings triaged against each workflow's `on:` trigger surface read
from `origin/main` at the scanned sha.

## Split: real vs false-positive

### REAL → issue #1594

- `yaml.github-actions.security.secrets-inherit.secrets-inherit` — `ci.yml:311`.
  `secrets: inherit` passes the **entire** caller secret set to the reusable `pipeline.yml`, which only
  consumes the caller's GH token (CWE-250). Remedy: explicit `secrets:` list on the callee.
- `yaml.github-actions.security.gha-workflow-env-secret.gha-workflow-env-secret` — workflow-level
  `env:` secret ambient for every job/step (CWE-732): `ci.yml:31-32`, `engine-bump.yml:34-35`,
  `pipeline.yml:41-42`, `registry-sync.yml:30-31`. Remedy: scope to the step that reads them.

### FALSE-POSITIVE class → issue #1595

- `yaml.github-actions.security.run-shell-injection.run-shell-injection` at **8** sites
  (engine-build:211, pipeline:220, publish-agent-image:133, queued-alarm:102, scope:98, security-bot:107,
  security-scan:126+144). Every flagged value is **trusted and quoted**, routed through a `make` step,
  on a trigger that is `workflow_dispatch`-only or `pull_request` — **never `pull_request_target`**:
  matrix constants, authorized dispatcher inputs, `github.repository`/`github.actor`/`github.base_ref`
  quoted into `make` calls. No untrusted fork code reaches the shell with secrets. Same family as the
  vendored-pack GH013 carve (#1282/#1284), not a real CWE-78 surface.
  Remedy: rescope the semgrep pairing/allowlist on these sites only — the rule still fires on real
  unquoted `${{ github.event.* }}` in a `pull_request_target` `run:` step. This is **not** a gate
  weakening: `fail_on`/severity untouched, no `require_fix:false`, no emptied `fail_on`.

## Not done (by design)

No workflow file edited (this lane files, tags, routes). Both issues carry the `security` label read
back and are OPEN, routed to the implementer queue. #1088 held; nothing armed.
