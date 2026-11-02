# 2026-11-02 — non-root runtime user for the CI variant image (issues #1593/#1597)

Issue: [#1597](https://github.com/asimov-agent/llgenie/issues/1597) (+ duplicate
[#1593](https://github.com/asimov-agent/llgenie/issues/1593)). The daily security-scan
(run 41461058238 / 41458285599) red at `scan` on
`dockerfile.security.missing-user.missing-user` at `containers/ci-variant/Dockerfile:49`
(region "requires login"). The image declared **no** `USER` directive, so the ephemeral `CMD`
ran as root.

## What changed

Added a trailing non-root `USER 65532:65532` to `containers/ci-variant/Dockerfile`, after the
last root-requiring `WORKDIR /repo` and before the `CMD ["--help"]`. This is the reserved
non-root UID (same as the semgrep scanner image) and is safe here because the image is
**build-only**: `make test-variant-image` builds it from a temp context and `VARIANT_RUN` is
never invoked by any target, and the `CMD` (`--help`) writes nothing / carries no HOME state.

## Why not a naive earlier drop

A `USER` cannot precede the `RUN apt-get install` / `pip install` / CUDA-driver-stub steps
(lines 19–47), which need root to write `/usr/lib` and the toolchain. The only thing that runs
as the declared user is the build-only `CMD`, so the trailing drop is exactly the right scope.

## Acceptance (verified)

- `grep '^USER'` now yields exactly one directive, `!= root`, and it is the last `USER` before
  `CMD`.
- The hardened Dockerfile builds (`make test-variant-image` shape, temp context with the
  regenerated lockfiles); build proof run recorded on the PR.
- `semgrep` over the committed `p/default` pack no longer reports `missing-user` for this file.
- No base image, toolchain, env, or `CMD` changed; the scan's `fail_on`/severity/policy are
  untouched (this is a hardening, not a gate widening).

Both #1593 and #1597 close on this fix (duplicate pair, per the planner dispatch / one-fix
ONE-vehicle #824 discipline).
