# Change: defer a CI-image publish in `pull_request` runs — build locally, publish at landing

## Why

A pull request that edits a CI image's Dockerfile or lockfile moves that image's content-hash
tag. Nothing publishes that tag during the PR run: the `ci-images` job builds it but cannot push
(a `pull_request` token is read-only to the base registry, issue #155), and every job that then
runs `make test-env` / `make test-image-pull` dies at `scripts/ci_images.py pull test` because
"CI jobs never build a CI image". Measured on PR #2517 (fork head): `lint`, `unit`, `install` and
`cpu-health` all went red at the `pull test` line while the image itself built green in
`ci-images` — the PR could not pass its own pipeline no matter what the change did, and main only
got the tag after the landing run. Same-repo PRs CAN publish mid-run (measured: PR #1738 moved
`containers/test/Dockerfile`, published mid-PR and merged green), so the gap is exactly: **a
`pull_request` run consumes an image that its own run can never publish for a fork head.**

The repo has already solved this shape twice: the OpenSpec gate pull-or-builds (`make
openspec-image`, "a fork PR cannot publish a NEW hash", issue #1673) and `engine-build` publishes
engine images only on `push` while PR runs build+test them. The test image is the last CI image
without the fallback.

A lane that demotes the consumer jobs instead was considered and rejected:
`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` bans job-level skip shapes, and every
leg step runs `make test-env` regardless — demotion would have to reach into all five legs' make
targets, while the pull-or-build fallback keeps every job running its REAL work against the image
it just built. Issue #2518's body carried the demotion sketch; this change is the referee (issue
body synced to it).

## What changes

- `scripts/ci_images.py::pull` gains an event-scoped deferral: when the pull fails, the tag is
  genuinely absent from the registry (`published()` lookup), and `GITHUB_EVENT_NAME ==
  "pull_request"`, it prints a `::warning title=publish deferred::` line naming the landing run's
  publish (issue #2518), then builds `llgenie/<name>:latest` locally from the same hashed context
  (the `ensure` build, factored into `_build_local`) and exits 0. Consumer legs then run their
  full work inside the locally built image.
- The hard failure stays everywhere else: `push` / `workflow_run` / manual runs still fail loudly
  on a missing tag ("CI jobs never build a CI image") — there the publish already ran. A
  `pull_request` run where the tag IS published but the pull itself fails (network, daemon) still
  fails: the deferral is only for genuinely unpublished tags.
- Makefile comment wording follows the new truth (`test-image-pull`, the `ci-<job>` seam comment);
  no target, recipe or workflow file changes.
- `tests/test_ci_images.py`: `_fake_docker` scrubs the inherited `GITHUB_EVENT_NAME` (the unit gate
  runs pytest on `pull_request` runners, where inheritance would flip the push-semantics tests) and
  gains a `pull_fail` knob; four tests pin the deferral, the PR pull of a published tag, the push
  hard-fail, and the PR published-tag-but-failed-pull hard-fail.

## Who

llgenie-ci-pipelines-maintainer (this lane owns the publish-order gap; issue #2518).
