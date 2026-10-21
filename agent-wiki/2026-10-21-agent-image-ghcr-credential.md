# 2026-10-21 — the agent image can publish: GITHUB_TOKEN, not the owner PAT

Issue: [#413](https://github.com/asimov-agent/llgenie/issues/413)
PR: [#441](https://github.com/asimov-agent/llgenie/pull/441)
OpenSpec change: `agent-image-ghcr-credential`

## What was wrong

`publish-agent-image.yml` logged in to GHCR with `secrets.BUMP_TOKEN` as `github.repository_owner`, and
its own pre-flight (#335) refused that credential in seconds:

```
[ci-images] push-check asimov-agent/llgenie/agent: the credential CANNOT push (403):
{"errors":[{"code":"DENIED","message":"permission_denied: The token provided does not match expected scopes."}]}
```

Measured on run 39420414201 (`feat/bot-model-1017`, 2026-10-20T12:11Z) and run 39538405507 (`main`,
2026-10-21T03:24Z): both stop at step 6 with the same 403; `make publish-agent-image` and `make
ci-image-refs` are skipped. The PAT carries no `write:packages`, so GHCR issues it a token without push
access.

The header's justification for that PAT — "the default token is DENIED *Create organization package*" —
never applied: `asimov-agent` is a **user** account (`gh api users/asimov-agent` → `type: User`).

## What the fix is

The repository already publishes to this namespace: `ci.yml`'s `ci-images` job pushes `llgenie/test` and
`llgenie/openspec` with `secrets.GITHUB_TOKEN` under `packages: write` (published tag
`llgenie/test:5e0bae123ac9`). Run 39421110083 proved the same shape works for the agent image — its
pre-flight answered `the credential may push — empty upload accepted (202)` and the job then pushed
`llgenie/agent:d70aa12310b4`.

So `publish-agent-image.yml` now logs in with `secrets.GITHUB_TOKEN` as `github.actor`, hands that same
token to `make agent-image-push-check`, and its header states the measured reason instead of the org
theory. `scripts/ci_images.py pushcheck`'s message and comment follow, the README paragraph matches, and
`tests/test_ci_images.py::test_the_agent_publish_logs_in_with_the_credential_its_push_check_proves` locks
login-secret == pre-flight-secret == `GITHUB_TOKEN` + `github.actor` + `packages: write`.

## Verification

- `tests/test_ci_images.py` — the new test beside the existing push-check tests (no mocks: the stub
  registry still records real HTTP shapes).
- `make test-unit` → 4910 passed; the 2 failures were the Hugging Face 429 link probes tracked by #435 and
  re-ran green in isolation (`tests/test_trend_pick.py`, 81 passed).
- `make check-workflows`, `make check-docs`, `make check-wiring`, `make check-dispatch-forms`,
  `make check-pr-hygiene`, `make check-pr-authors`, `make lint`,
  `make openspec-validate NAME=agent-image-ghcr-credential`.
- **Live**: dispatched on this branch — run 39540690264 is green. Its pre-flight answered `the credential
  may push — empty upload accepted (202)` and the publish then no-opped, because the hash tag
  `llgenie/agent:d70aa12310b4` was already on GHCR (the hash covers the Dockerfile and install script,
  neither of which this change touches). The same job on `main` refuses the old credential in 29 seconds,
  run 39538405507.

## Consequences

A bot job can pull the image built from its own commit instead of spending ~6–10 minutes rebuilding Hermes
on the runner, and the #405 model pin can finally reach the bots.
