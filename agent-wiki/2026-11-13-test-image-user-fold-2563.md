# Test-image user fold: the last DS-0002 closes (issue #2563, PR #TODO)

## What was verified

- `containers/test/Dockerfile` was the last Dockerfile in the tree without a
  `USER` instruction — the only remaining trivy `DS-0002` finding (#2576) of the
  tree-wide non-root sweep (#2504). It now ends with `USER 1000:1000`, carries
  `ENV HOME=/tmp`, and moved `safe.directory '*'` to the SYSTEM gitconfig
  (`git config --system`) so `git ls-files` works for any runtime uid.
- `Makefile TEST_OPTS` replaced `-u root -e HOME=/root` with
  `-u "$(shell id -u):$(shell id -g)"`: plain test stages write into the
  bind-mounted checkout as the checkout's owner (uid 1000 on this host == the
  image default; the CI runner's uid on GitHub). `pytest` bytecode/cache writes
  no longer land root-owned on host.
- `ENGINE_TEST_ARGS` KEEPS `-u root` on purpose: that container reaches the host
  docker daemon through `/var/run/docker.sock`, `srw-rw---- root:docker` on this
  host; the mapped uid could not connect. `CI_HOME_CLEAN` keeps `-u root`
  because `.ci-home` is a root-owned tree from the engine stages. Both reasons
  are stated in the Makefile and locked by tests.
- Test locks added in `tests/test_ci_images.py`:
  `test_the_test_image_ships_non_root` and
  `test_plain_container_stages_run_as_the_checkout_owner`.

## Key decision

The fold was deferred out of the #2517 sweep because the Dockerfile is the hash
input of the published `llgenie/test` tag. With the #2518 deferral lane on main
(`ci_images.py pull` builds a moved, unpublished tag locally inside
`pull_request` runs), the fold PR itself becomes the lane's live proof: the tag
moves from `7df351360413`, the PR run defers, the landing run publishes.
Measured note: the fold rides a SAME-REPO PR head (the 2026-11-12 trigger guard
refuses fork heads); the deferral is event-scoped, so the head repo does not
matter.

## Current status

Driven by issues #2563 (goal mirrored in the issue body) and #2576 (closed by
the same PR). Implemented on `feat/test-image-user-fold`; local proof and the
live deferral proof are recorded on the issue.
