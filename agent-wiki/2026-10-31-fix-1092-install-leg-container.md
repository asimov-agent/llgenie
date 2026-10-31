# 2026-10-31 — test-engine-install installs the launcher, not a host skill install (#1027, fixes #1092)

`make test-engine-install` (the internal CI seam the engine-build producer owns, gated on
`inputs.push == 'true'`) ran `make engine-install` to bring the freshly-published engine onto the
probe host. `engine-install` is the full host skill install path (needs a skill bundle, config, an
SSH-style host), which is the wrong vehicle for a container-verified engine: the producer only
needs the runtime launcher scripts on the probe host's `~/bin/` so `test-built-engine` can report
the installed version.

## What changed

- `Makefile` `test-engine-install:`
  - Before: `make engine-install ENGINE="$(ENGINE)" BACKEND="$(ARCH)"` — the full host install leg
    that the skill-install path needs.
  - After: `make engine-launchers ENGINES="$(ENGINE)" ARCH="$(ARCH)"` — installs just the engine
    launchers, the surface `test-built-engine` / `ci-install-dry` actually exercise.

The rest of the leg is unchanged: `make test-built-engine`, `make ci-install-dry`,
`make ci-install-uninstall` (the uninstall must remove the just-published image). The narrow
`engine-launchers` call is the correct inner step for the container-verified install leg and
matches what #1092's original failure was isolating.

Issue: #1092 · PR: #1093
