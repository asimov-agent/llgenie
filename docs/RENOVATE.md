# Renovate — what it owns, and what it must never touch

[`renovate.json`](../renovate.json) is acted on unattended, so the properties this repository
depends on are checked by `make check-renovate` (inside `make ci-unit`) rather than trusted. This
page is the reference for a reviewer reading a Renovate PR and for the person changing the config.

## What Renovate owns

| Ecosystem | Files | Manager |
|---|---|---|
| Python pins | `tools/requirements.in` (compiled to `tools/requirements.txt`) | `pip_requirements` + `pip-compile` |
| Container base images | `Dockerfile`, `docker-compose*.yml` (`containers/**`, root) | `dockerfile` / `docker-compose` |

**Only the `.in` files are validated as sources.** `tools/requirements.in` and
`tools/requirements-dev.in` are the single sources of truth; the compiled
`tools/requirements*.txt` are **generated** (`make generate-requirements`) and are never a
`pip_requirements` source. Renovate's `pip-compile` manager **regenerates** the `.txt` from the
`.in` during a bump, so a bump PR shows the `.in` edit and its compiled output — the rule
AGENTS.md states for every other contributor. `renovate.json` says so explicitly:
`pip_requirements.fileMatch` matches only `requirements*.in`, and `pip-compile.fileMatch` matches
only `requirements*.txt` as its OUTPUT. `make check-renovate` fails when a `pip_requirements`
match names a `.txt` (a compiled file treated as a source) or when no `.in` source is matched.

## What it must never touch

`ignorePaths` in the config:

- `data/models.json` — the vendored registry, replaced wholesale by `make sync-registry`.
- `containers/engines/dockerfiles/**`, `containers/engines/params/**` — written only by
  `make generate-engine-params` from the skills. Editing one directly is a generated-file edit.
- `containers/scanners/digests.json` — the scanner digests the scan workflow pins by digest.
- `containers/ci-variant/**` — the variant-build image's directory, and now its `Dockerfile` alone:
  the lockfiles it builds from are `tools/requirements*.txt`, copied in at build time (issue #787),
  so a bump belongs on the `tools/` chain and never here.

GitHub Actions are **disabled** for Renovate (`matchManagers: ["github-actions"]` →
`enabled: false`). Actions move through `make update-actions` with a reviewed tag diff; see
[`docs/SECURITY.md`](SECURITY.md).

## The merge policy

- **Automerge is low-risk only:** `patch`, `pin`, `digest`, and only for Python pins.
- Every automerge rule sets `automergeType: pr` and `platformAutomerge: false`, so the PR is
  created and then must pass this repository's required checks. CI's `auto-merge` job remains the
  single thing that lands a PR — Renovate never opens a second merge path.
- **Container base-image bumps never automerge.** A base image changes what every image is built
  from; its build is the review.
- Major/minor Python bumps never automerge.

## Why a base-image bump builds images

`.github/workflows/ci.yml`'s `pull_request` trigger carries no `paths:` / `paths-ignore:` filter
and declares the `engine-image` matrix, so **any** PR — Renovate's included — builds and
post-build-tests the engine images. `scripts/check_renovate.py` asserts both facts (the absence of
a filter and the presence of the job), so a future optimisation that path-filters the pipeline
fails `make ci-unit` instead of silently skipping the build a base-image bump needs.

## Reproducing a Renovate PR locally

```bash
git fetch origin pull/<n>/head:renovate-pr && git switch renovate-pr
make check-renovate            # the config gate
make test-unit                 # the same hermetic gate CI runs
make build-engine ENGINE=llama.cpp ARCH=cpu   # for a base-image bump: the image the PR changes
```

## Targets

| Target | What it does |
|---|---|
| `make check-renovate` | **Fails** when the config automerges more than low-risk updates, drops `platformAutomerge: false`, may edit a generated/vendored file, turns `pip-compile` off, lets Renovate own the Actions, or when `ci.yml` path-filters the pipeline. Part of `make ci-unit`. |
| `make renovate-report` | Prints every package rule with its managers, automerge state, update types, and the ignored paths. |
