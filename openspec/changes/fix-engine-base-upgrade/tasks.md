# fix-engine-base-upgrade — tasks

Umbrella issue: [#2839](https://github.com/asimov-agent/llgenie/issues/2839)

- [x] 1. `scripts/engine_skills.py::render_base_dockerfile` emits
  `apt-get upgrade -y` between `apt-get update` and the build-toolchain
  `apt-get install` for every backend (cpu, cuda, rocm, vulkan).
- [x] 2. `make generate-engine-params` regenerates the on-disk files: all four
  `containers/engines/base/Dockerfile.<backend>` carry the upgrade layer and
  every engine Dockerfile's `FROM llgenie/base-<backend>:<hash> AS build` pins
  the new base tag; `make check-engine-params` is green (0 stale).
- [x] 3. The unit suite is green at this head, including the existing engine
  matrix tests (make test-unit rc=0, no skips).
- [x] 4. Documentation: `agent-wiki/2026-11-16-fix-engine-base-upgrade-2839.md`
  references issue #2839, and the `CHANGES.md` index gains the row; `make
  check-docs` rc=0.
- [x] 5. `make lane-preflight` green (lint, check-workflows, check-wiring,
  check-docs, check-pr-hygiene, openspec-tasks-check) and `make
  openspec-validate NAME=fix-engine-base-upgrade` rc=0, with every task above
  ticked; the PR (`closes #2839`) carries this checklist mirrored.
