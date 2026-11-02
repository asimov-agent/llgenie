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

### THIRD root cause (a real pipeline defect) → issue #1598

A corrective report-only dispatch (run **41461058238**, `enforce=report`, scanned sha `99874a46`)
red even though report mode is meant to be non-gating. The cause was not a finding: `make security-issues`
created finding **#1597** (`dockerfile.security.missing-user.missing-user`, `containers/ci-variant/Dockerfile:49`,
high) and then the labeling write failed verbatim:

```
[security-issues] could not label #1597: gh: Resource not accessible by personal access token (HTTP 403)
make: *** [Makefile:1175: security-issues] Error 1
```

The step's token 403s on the label write, so the freshly-created finding is left **unlabelled** —
invisible to `security-bot` (it picks ONE issue per run by label). This is the "created but never routed"
failure class (#724, #781-784), now tracked as **#1598**. #1597 was hand-re-labelled (security,
severity:high, component:container, read back) to keep it visible while a fix lands.

## Outcome

- Issues **#1594**, **#1595**, **#1598** filed and `security`-tagged (read back, OPEN), routed to the
  implementer queue. **#1597** repaired in place.
- Triage record committed via PR **#1596**, merged by owner (mergeCommit `aef61e17`, 2026-11-02T14:21:31Z).
- This extension (third root cause + repair) committed via PR, merged.

## Not done (by design)

No workflow file edited (this lane files, tags, routes). The fixes for #1594/#1595/#1598 route to the
implementer queue. The `security-scan` workflow re-reds DAILY until those land (findings still in the
tree); the label-403 gap is the part that also buries the filing path. #1088 held; nothing armed.
