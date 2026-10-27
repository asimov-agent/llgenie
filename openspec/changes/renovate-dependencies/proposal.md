# renovate-dependencies — proposal

Issue: [#718](https://github.com/asimov-agent/llgenie/issues/718)
Parent: [#713](https://github.com/asimov-agent/llgenie/issues/713)

## Why

`renovate.json` does not exist (`ls renovate.json` → No such file). The Python pins live in
`tools/requirements.in` → compiled `tools/requirements.txt`, and container bases live in
`containers/engines/base/Dockerfile.*` and `containers/*/Dockerfile`. Nothing keeps them fresh,
and a naive config would do two things this repository forbids: hand-edit a compiled
`requirements*.txt` (AGENTS.md: regenerate, never hand-edit), and bump a base image without the
image build and its tests being the review.

## What Changes

- **`renovate.json`**: `config:recommended` preset, `pip_requirements` + `pip-compile` for Python
  (the `.in` is edited, the `.txt` recompiled), `dockerfile`/`docker-compose` for base images,
  one grouped PR per ecosystem, and `ignorePaths` for everything generated or vendored.
- **Conservative automerge**: `patch`/`pin`/`digest` Python updates only, `automergeType: pr`,
  `platformAutomerge: false` — CI's `auto-merge` job stays the single landing authority.
  Container base-image bumps never automerge.
- **GitHub Actions stay Renovate's non-business**: `github-actions` is disabled; pins move through
  `make update-actions` with a reviewed tag diff (the `pin-github-actions` change).
- **`scripts/check_renovate.py`** + `make check-renovate` / `make renovate-report`, with
  `check-renovate` in `make ci-unit`: the config cannot grow a second merge path, drop an
  `ignorePath`, turn `pip-compile` off, or hand the Actions to Renovate without failing the gate.
  The same gate asserts `ci.yml` has **no** `paths:` filter on `pull_request` and declares the
  `engine-image` job, so a base-image PR always builds the images instead of skipping them.
- **`docs/RENOVATE.md`** — ownership, the never-touch list, the merge policy, how a base-image
  bump reaches the image build, and how to reproduce a Renovate PR locally. Linked from
  `README.md`.
- **`tests/test_renovate_config.py`** — every rule proven on a fixture tree, then the real config
  asserted clean.

## Not covered

- Renovate for GitHub Actions (deliberately disabled; see #719's `docs/SECURITY.md`).
- Upstream engine version pins (`make engine-bump`) — a separate existing pipeline.
- A dependency bot for the scanner images' own tool versions (#714 owns their pins).
