# Test-image user fold: containers/test/Dockerfile runs non-root

## Why

`containers/test/Dockerfile` is the last Dockerfile in the tree without a `USER`
instruction, so it is the last trivy `DS-0002` finding (issue #2576) blocking the
tree-wide non-root sweep (#2504). The fold was pulled out of the #2517 sweep
because the Dockerfile is the hash input of the published `llgenie/test` tag: a PR
that edits it moves a tag that PR can never publish. Issue #2518 landed the
deferral lane (`ci_images.py pull` builds the moved tag locally inside
`pull_request` runs); the fold itself is still not done, so the lane has no live
proof from a real PR either (issue #2563).

## What Changes

- `containers/test/Dockerfile` ships non-root: `USER 1000:1000` as the final
  instruction, `ENV HOME=/tmp` (a world-writable HOME for the mapped uid), and the
  repo-wide git `safe.directory` moves from the root-only global config to
  `git config --system` (`/etc/gitconfig`, world-readable) so `git ls-files` still
  works as the mapped uid.
- `Makefile TEST_OPTS` stops forcing root: `-u root -e HOME=/root` becomes
  `-u "$(shell id -u):$(shell id -g)"` — the container runs as the uid that owns
  the bind-mounted checkout (host uid 1000 == the Dockerfile default; CI runner
  uid 1001 can write `/repo`). Engine-driven stages (`ENGINE_TEST_ARGS`) keep
  `-u root` unchanged: their container must reach the host docker socket
  (`srw-rw---- root:docker` on this host), which the mapped uid cannot.
- The deferral lane gets its live proof: this PR moves the `llgenie/test` content
  hash (from `7df351360413`), so its own `pull_request` run must print
  `::warning title=publish deferred::` and every test-env leg goes green on the
  locally built image; the landing run publishes the new tag.

## Impact

- Affected specs: `ci-test-image` (ADDED requirement: the test image serves non-root)
- Affected code: `containers/test/Dockerfile`, `Makefile` (`TEST_OPTS`), tests
  pinning the container shape, docs pair (agent-wiki + changes.d row).
