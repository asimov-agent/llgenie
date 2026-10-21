# agent-image-ghcr-credential — proposal

Issue: [#413](https://github.com/asimov-agent/llgenie/issues/413)

## Why

`publish-agent-image.yml` cannot publish anything. Its own pre-flight (#335, `make
agent-image-push-check`) refuses the credential it logs in with, in seconds, before the build:

```
[ci-images] push-check asimov-agent/llgenie/agent: the credential CANNOT push (403):
{"errors":[{"code":"DENIED","message":"permission_denied: The token provided does not match expected scopes."}]}
```

Measured on two dispatches: run 39420414201 (`feat/bot-model-1017`, 2026-10-20 12:11Z, 33s) and run
39538405507 (`main`, 2026-10-21 03:24Z, 29s) — the same 403, both failing at step 6 while steps 7
(`make publish-agent-image`) and 8 (`make ci-image-refs`) are skipped. Every dispatch since #338 landed
(2026-10-16) has died here.

The credential is `secrets.BUMP_TOKEN`, logged in as `github.repository_owner`. The registry's message is
the verdict: that PAT carries no `write:packages`, so GHCR issues it a token with no push access and
refuses the upload. The header's justification for the PAT ("the default token is DENIED *Create
organization package* for a brand-new package") never applied: `gh api users/asimov-agent --jq .type` →
`User`, not an organization.

The same repository already publishes `llgenie/test` and `llgenie/openspec` to that very namespace, from
`ci.yml`'s `ci-images` job, with `secrets.GITHUB_TOKEN` + `packages: write` — proven by the published
`llgenie/test:5e0bae123ac9` tag and by run 39421110083, whose publish job logged in that way and whose
pre-flight answered `the credential may push — empty upload accepted (202)`, then built and pushed
`llgenie/agent:d70aa12310b4`.

So the fix is not a new credential and not a new secret: it is to log in — and to prove the push — with the
credential and account this repo already publishes with.

## What Changes

- **`publish-agent-image.yml`**: the GHCR login step uses `secrets.GITHUB_TOKEN` as `github.actor`
  (ci.yml's shape; `packages: write` is already declared on the job) instead of `secrets.BUMP_TOKEN` as
  `github.repository_owner`; the pre-flight step is handed that same token
  (`GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}`); the header's stale "organization package" reasoning is
  replaced with the measured 403, so the next reader is not sent after an org permission that does not
  exist.
- **`scripts/ci_images.py pushcheck`**: the missing-credential message names `secrets.GITHUB_TOKEN` (not the
  owner PAT), and the default Basic user's comment matches the job (`github.actor`) instead of the
  repository owner.
- **`tests/test_ci_images.py`**: one new test locks the invariant that failed here — the secret the login
  step names is the secret the pre-flight is handed, it is `GITHUB_TOKEN`, the login account is
  `github.actor`, and the job declares `packages: write`.
- **`README.md`**: the `publish-agent-image.yml` paragraph describes the credential it really uses, with the
  issue number and the registry's refusal, replacing the "owner PAT" claim.
- **`agent-wiki/2026-10-21-agent-image-ghcr-credential.md`**: the dated work record for this change.

## Not covered

- The live publish itself. `workflow_dispatch` can only be dispatched against a ref that exists in
  `asimov-agent/llgenie`, so this fork branch cannot be dispatched from here; the fix is verified by the
  hermetic tests, `make check-workflows`, and the recorded 202 of run 39421110083, which ran this exact
  credential shape. Landing it is what makes the next dispatch able to publish.
- Auditing every other workflow's GHCR secret: #420 is the "each write uses the token that can perform it"
  pass. `secrets.BUMP_TOKEN` stays in the repo — other bot workflows use it for writes that are not
  package pushes.
- #329 — actionlint's shellcheck findings across the workflows, including this one.

Refs: #335/#338 (the pre-flight that caught this), #222/#238/#248 (the agent image and its publish path),
#405 (the model pin whose image never reached the bots because this could not publish), #420.
