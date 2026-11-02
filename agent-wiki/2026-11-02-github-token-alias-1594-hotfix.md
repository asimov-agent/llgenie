# recurse the GITHUB_TOKEN alias in the reusable-workflow secrets contract

## Defect

PR #1618 (issue #1594) broke `main`'s CI at load: it replaced `secrets: inherit` with an
explicit `secrets:` block and declared a secret literally named `GITHUB_TOKEN` under
`pipeline.yml`'s `on.workflow_call.secrets`. GitHub refuses that — "secret name GITHUB_TOKEN
within workflow_call can not be used since it would collide with system reserved name" — so
every `pull_request` and `push` run of `ci.yml` failed at compile with ZERO jobs, a run whose
`name` is the file path and no log (the #330/load-rejection signature; measured on run
41529052935 at main `8490c23f`).

## Fix

Alias the token at the reusable-workflow call boundary, the only spelling GitHub accepts:

- `ci.yml` caller passes `RUN_TOKEN: ${{ secrets.GITHUB_TOKEN }}` in the explicit `secrets:`
  block (never a key named `GITHUB_TOKEN`).
- `pipeline.yml` callee declares `RUN_TOKEN` under `on.workflow_call.secrets` (both optional so
  a caller that passes neither still parses) — and never `GITHUB_TOKEN`.
- The two Hub-touching jobs (`cpu-health`, `top-tier`) re-export it as `GITHUB_TOKEN` in their
  job-level `env:`: `GITHUB_TOKEN: ${{ secrets.RUN_TOKEN }}`, so the Makefile
  `docker run -e GITHUB_TOKEN` forwarding chain is untouched.

## Verification

- `actionlint` clean on all four workflows.
- The caller's mapping `{HF_TOKEN, RUN_TOKEN}` is a subset of what the callee declares
  `{HF_TOKEN, RUN_TOKEN}`; `GITHUB_TOKEN` appears in neither the caller mapping nor the callee
  declaration.
- 89 tests pass in the CI container (reworked shape tests assert the alias); `make lint`,
  `make check-workflows`, `make check-docs` all rc=0 on the branch.
- Live CI at the PR head (`14e36597`) compiles and runs all real jobs — `linux/unit`, lint,
  openspec, install, agents-read, cpu-health, top-tier — restoring the 0-job compile failure.

No gate weakening: the explicit non-`inherit` mapping stays (issue #1594); `secrets: inherit`
is not reintroduced; no fail_on/severity/allowlist change.
