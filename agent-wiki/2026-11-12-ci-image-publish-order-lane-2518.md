# CI-image publish deferral in `pull_request` runs (issue #2518)

Date: 2026-11-12 · Branch: `feat/ci-image-publish-order-lane` · OpenSpec: `ci-image-publish-order-lane` · Issue: #2518 · PR: #2564

## What was verified against the spec

The deadlock (measured on PR #2517, fork head `09f814f79`): editing
`containers/test/Dockerfile` moves the content-hash tag `test:<hash>`; a `pull_request`
token cannot publish it (issue #155); `ci-images` SKIP-publishes; then `lint`, `unit`,
`install`, `cpu-health` all die at `python3 scripts/ci_images.py pull test`
("CI jobs never build a CI image"). The PR cannot pass its own pipeline; only the
landing run gets the tag.

The landed lane (`scripts/ci_images.py::pull`):

- failed pull + `published()` proves the tag is absent + `GITHUB_EVENT_NAME ==
  "pull_request"` → print `::warning title=publish deferred::` naming the landing
  publish (issue #2518), `_build_local` the same Dockerfile/lockfile context as
  `ensure`, exit 0. Consumer legs then run their REAL work in the built image.
- push / workflow_run / manual runs keep the hard failure (the publish already ran
  there); a `pull_request` run with a PUBLISHED tag but a failing pull still reds —
  the deferral only fires for genuinely unpublished tags.
- The event check short-circuits before the registry lookup, so push-run behavior
  (and its logs) are byte-identical to before.
- `ensure` (dev host) behavior unchanged; the build is now factored into
  `_build_local(name, root)`.
- Makefile comment wording (`test-image-pull`, the `ci-<job>` seam) states the event
  scope. No target body and no workflow file changed.

Design decision (referee over the issue's earlier demotion sketch): demoting
consumer jobs was rejected — `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`
bans job-level skip shapes and every leg runs `make test-env` regardless. The repo
already pull-or-builds the OpenSpec gate (`make openspec-image`, issue #1673) and
publishes engine images only on push; this change gives the test image the same
fallback. Issue body synced to this design.

## Evidence

- `pytest tests/test_ci_images.py -q` → 40 passed, rc=0 (4 new tests pin deferral /
  PR-pull / push hard-fail / published-tag-failed-pull).
- 12-module consumer sweep importing `ci_images`: 381 passed; the 1 failure
  (`test_every_image_install_pulls_is_published`, live GHCR) reproduces identically on
  a detached `origin/main` worktree — engine fleet dispatches still pending; fixed by
  PR #2562 + the #2529 sweep, not this change's files.
- `make openspec-validate`, `make check-wiring`, `make check-workflows` all rc=0.
- Same-repo mid-PR publishing measured historically (PR #1738 moved
  `containers/test/Dockerfile` and merged green), so the deferral is scoped to the
  genuinely-unpublished case, not to PRs in general.

## Current status

Implementation committed on `feat/ci-image-publish-order-lane`; PR opened against
upstream main with `closes #2518`. The `USER 1000:1000` fold of
`containers/test/Dockerfile` (last tree-wide trivy `DS-0002`) is deferred to its own
fork-head PR issue, which doubles as the live proof that a fork-head PR riding this
lane goes green.
