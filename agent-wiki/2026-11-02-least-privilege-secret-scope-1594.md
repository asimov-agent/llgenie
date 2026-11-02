# least-privilege secret scope: kill `secrets: inherit` + workflow-level env secrets

## Defect

The daily security-scan (run 41458285599 at `febd964613b8`) reds on two semgrep findings
that are genuine least-privilege defects, not scanner noise:

- `yaml.github-actions.security.secrets-inherit.secrets-inherit` — `ci.yml:311` (then) passed
  **every** repository secret to the reusable `pipeline.yml` via `secrets: inherit` (CWE-250,
  semgrep ERROR/HIGH): the callee received the whole repository secret store when it consumes
  only `HF_TOKEN` and `GITHUB_TOKEN`.
- `yaml.github-actions.security.gha-workflow-env-secret.gha-workflow-env-secret` — four
  workflows exposed `HF_TOKEN` and `GITHUB_TOKEN` at **workflow-level** `env:` (ci.yml:31-32,
  engine-bump.yml:34-35, pipeline.yml:41-42, registry-sync.yml:30-31), making each secret
  ambient for every job and every step (CWE-732, semgrep HIGH): a token an engine step needs
  was also readable by `checkout`, `make`, and arbitrary shell in unrelated jobs.

## Fix

- `ci.yml`: replace `secrets: inherit` with an explicit `secrets:` block naming the two
  secrets the `pipeline.yml` callee actually consumes (`HF_TOKEN`, `GITHUB_TOKEN`); remove the
  workflow-level `env:`.
- `pipeline.yml`, `engine-bump.yml`, `registry-sync.yml`: remove the workflow-level `env:` and
  declare each token in the **job-level** `env:` of exactly the job(s) that run Hub/token-
  touching make targets:
  - `pipeline.yml`: `cpu-health` and `top-tier` (the two rows that download/serve a real model
    and hit the Hub/API); the hermetic `lint`/`unit`/`install`/`agents-read`/`openspec` jobs get
    no ambient token.
  - `engine-bump.yml`: the `bump` job (engine derive + TensorFold live archive in the test
    container, which forwards the tokens by name via Makefile `TEST_OPTS`);
  - `registry-sync.yml`: the `sync` job (Hub sync + test image).
- The container-forwarding chain is untouched: `docker run -e HF_TOKEN -e GITHUB_TOKEN`
  (`Makefile TEST_OPTS`) still copies each token from the runner env — now scoped to the job
  that owns the container, not ambient to the run.

## Tests

`tests/test_hf_auth.py::test_workflows_inject_the_actions_secret` and
`tests/test_engine_bump.py::test_workflows_export_the_github_token` asserted the OLD shape
(workflow-level `env:`) and `secrets == "inherit"`; they now assert the NEW least-privilege
shape (no token in a top-level `env:`; the owning job holds it). Verified:
- all 4 edited workflows parse as valid YAML; `make lint` rc=0; `make check-docs` rc=0.
- the reworked shape tests pass (42 passed in the test container, incl.
  `test_workflows_valid.py::test_every_committed_workflow_has_a_runnable_shape`);
- `tests/test_ci_images.py` and `tests/test_workflow_guards.py` still pass.
- the 23 `test_engine_bump.py` failures are pre-existing live-GitHub-API tests (`git stash`
  on this tree still fails the same test); they do not touch the workflows this change edits.

## Acceptance (from #1594)

- `ci.yml` no longer uses `secrets: inherit` (explicit secret list in place). ✅
- No flagged workflow carries a secret in a top-level (workflow) `env:` block. ✅
- A security-scan re-dispatch wraps green on the `secrets-inherit` and
  `gha-workflow-env-secret` rule ids at the new sha (it is never a PR check; `enforce=report`).

No gate weakened: no `fail_on`/severity set touched, no allowlist entry added, `make
check-security-scan` contract unchanged. The docs trio (#1123): this note + a `docs/changes.d/`
row + regenerated `CHANGES.md` ride the closing PR.
