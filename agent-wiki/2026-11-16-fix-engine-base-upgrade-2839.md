# 2026-11-16 — fix-engine-base-upgrade (#2839)

## What

The shared engine base renderer `scripts/engine_skills.py::render_base_dockerfile`
now runs `apt-get upgrade -y` between `apt-get update` and the build-toolchain
`apt-get install` on every backend (cpu, cuda, rocm, vulkan). The composed
engine base images previously re-shipped the debs their upstream bases
(`nvidia/cuda:13.0.2-devel-ubuntu24.04`, `ubuntu:24.04`) baked in, so every
rebuilt engine image kept the same 15 HIGH inherited findings (gnupg family,
libapt-pkg6.0t64, libssl3t64, openssl) measured on published-image scan run
43787049546.

## Decisions

- One renderer change, never a hand-edit of the generated
  `containers/engines/base/Dockerfile.<backend>` files. The base tag is the
  SHA-256 of the rendered Dockerfile, so `make generate-engine-params`
  regenerated all four bases and re-pinned every engine Dockerfile's
  `FROM llgenie/base-<backend>:<hash>` line; `make check-engine-params` keeps
  the on-disk copies and the renderer in lock-step.
- The upgrade sits in the same chained `RUN` as the toolchain install, matching
  the standing-upgrade shape the agent image Dockerfile adopted in #2836/#2838.
- The 15 findings close via the post-merge rebuild + next published-image scan
  (#2706 lane), never by hand; the `agent:latest`/`test:latest` container
  findings remain the #2836/#2838 + #2837 chain's scope.

## Status

Change implemented and regenerated; gates run/verified. PR implements #2839
(`closes #2839`).
