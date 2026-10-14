# Publishing the agent image: the credential that can create the package

Related: issue #238 (the agent image), the `publish-agent-image` workflow, PR that fixes it.

## What was wrong

`make publish-agent-image` (via the `Publish agent image` workflow) built the Hermes image for ten
minutes and then died on the push:

```
#11 ERROR: failed to push ghcr.io/asimov-agent/llgenie/agent:adb502fa87cc:
  denied: permission_denied: The token provided does not match expected scopes.
```

The workflow logged in with the owner PAT (`secrets.BUMP_TOKEN`) as
`-u "${{ github.repository_owner }}"` — the ORGANISATION name — and the comment claimed the default
`GITHUB_TOKEN` was denied for a brand-new package. Both halves were wrong.

## What the registry actually says

Measured directly against GHCR with a credential that does carry `write:packages`:

| probe | result |
|---|---|
| `GET /v2/asimov-agent/llgenie/test/tags/list` | **200** — `e1951ad87a5a`, `buildcache`, `5e0bae123ac9` |
| `GET /v2/asimov-agent/llgenie/openspec/tags/list` | **200** |
| `GET /v2/asimov-agent/llgenie/strata/tags/list` | **200** — `cuda`, `rocm` |
| `GET /v2/asimov-agent/llgenie/agent/tags/list` | **404** — the package does not exist |
| `POST /v2/asimov-agent/llgenie/agent/blobs/uploads/` | **403** `permission_denied: create_package` |

So the same org namespace is full of packages that **this repository's own workflows created with
the default `GITHUB_TOKEN`**, and `llgenie/agent` — the one image published through a PAT — is the
only one missing. The account is an outside collaborator on the org (its membership lookup 404s),
so its PAT may not create an org package; the workflow's `GITHUB_TOKEN` may.

## The fix

1. The login uses the **default `GITHUB_TOKEN`** with `packages: write` (already in the workflow):
   `echo "${{ github.token }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin`.
   The username is the triggering actor, not the org.
2. A **pre-flight** proves the credential can push BEFORE the build:
   `make agent-image-push-check` → `scripts/ci_images.py check-push agent` asks for a
   `:push`-scoped GHCR token and initiates an empty blob upload. Denied is now a seconds-long,
   named failure (`push DENIED … create_package`) instead of a ten-minute build that dies.

## Proof

The pre-flight itself, run against the registry, reproduces the condition the workflow used to hit
only at the end of a build. The publish is then verified by dispatching the workflow.

## Lesson

A publish is a privileged write: prove the credential can perform THAT write, with the registry's
own verdict, before doing any work that costs minutes. "The token is set" is not evidence that the
token may create the package.
