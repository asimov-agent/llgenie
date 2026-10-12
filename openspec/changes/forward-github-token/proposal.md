# fix(ci): forward GITHUB_TOKEN into the test containers

Issue: [#199](https://github.com/asimov-agent/llgenie/issues/199)

## Why

`make test-engine-bump-live` runs inside `llgenie/test`. The Linux runners start
that container with `-e HF_TOKEN` only. `_release_assets` then calls
`api.github.com` with no `Authorization` header and turns every error into an
empty asset list. The Linux unit job on run 38247208919 failed that way for
TensorFold v1.0.5 while the release still had its six archives.

## What Changes

- Workflows that already export `HF_TOKEN` also export `GITHUB_TOKEN` from
  `secrets.GITHUB_TOKEN`.
- The Linux test container and the Linux engine-test container forward
  `GITHUB_TOKEN` and `GH_TOKEN` by name (`-e`), the same way they forward
  `HF_TOKEN`. The value stays in the environment.
- `_release_assets` sends `Bearer` for the first non-empty of `GITHUB_TOKEN`,
  `GH_TOKEN`. A 401 or 403 on that call is retried once with no
  `Authorization` header, because an installation token is scoped to this
  repository and GitHub denies it on another public repository. Any other
  failure still returns no assets.

## Impact

- `scripts/engine_bump.py`
- `Makefile`
- `.github/workflows/{ci,pipeline,published,engine-bump,registry-sync}.yml`
- `tests/test_engine_bump.py`
- `README.md`
