# `linux / openspec` pulls or builds the OpenSpec CLI image — not a strict pull (issue #1673)

`make openspec-image-pull` (Makefile:1394) is a strict gate: it fails if the image hash is not on
GHCR and never builds. `scope.yml`'s docs gate deliberately stopped using it in favour of
`make openspec-image` (Makefile:1391: pull-or-build), because a fork PR's read-only `GITHUB_TOKEN`
cannot publish a NEW openspec image hash to the org's packages (`ci_images.py`'s `WRITE_DENIED`,
issue #1673) — a hard pull would red the gate for a write GitHub will never grant.

The `linux / openspec` job in `pipeline.yml` was the one remaining consumer of the strict target:
after a rebase that changes `openspec/Dockerfile` (a new hash), the `ci-images` publish is denied on
a fork PR, so the job reds on `ghcr.io/.../openspec:<hash> is not published` before its
`ci-openspec` validation ever runs. This change makes that job call `make openspec-image` too,
mirroring `scope.yml`, so it pulls the published hash when it exists and otherwise builds the
change's own Dockerfile.

`tests/test_ci_images.py::test_openspec_gate_uses_pull_or_build_mirroring_scope` pins the seam for
both `pipeline.yml` and `scope.yml`, so a regression back to a strict `pull` fails CI and repeats
the #1655 fork-PR red.
