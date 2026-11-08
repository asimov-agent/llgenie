# Prove the Hermes agent image carries every llgenie lane (issue #2181)

## Why

`containers/agent/Dockerfile` is the container every bot lane runs in, but as of issue #2181 it
carried ZERO references to `agents/` or to profiles. The image installed the Hermes CLI (and git,
gh, docker, the Nerve supervisory layer) but no lane: a bot job that asked for a named profile
resolved against an empty `${HERMES_HOME}/profiles`, so whatever rulebook a lane was supposed to
run under was simply not there. The defect was invisible at build time and only appeared inside a
bot run — an image that claims to run the fleet and holds none of it.

## What changes

The build now installs the fleet's lanes into the image and refuses to build one that is missing
a lane:

- `containers/agent/Dockerfile` COPYs the `agents/` tree into the image
  (`/opt/llgenie/agents`) and, in a new build `RUN`, installs each lane that
  `agents/manifest.json` declares into `${HERMES_HOME}/profiles/<name>/` (SOUL.md + skills),
  mirroring the host's `make sync-agent-profile`.
- `scripts/agent_lanes_check.py` — a new, hermetic gate the build RUNS after the install — reads
  the same manifest against the installed profiles and FAILS the build, naming any declared lane
  that did not land. A missing lane reds the build, not a later bot run.
- `scripts/ci_images.py` adds the whole `agents/` tree (and `scripts/agent_lanes_check.py`) to the
  agent image's hash inputs, so a changed SOUL.md or skill moves the `llgenie/agent` image tag — a
  stale image that still runs an old lane set is visible in its tag, not silently pulled forever.
  `context()` places the tree in the build context under `agents/` preserving subpaths (a flat
  copy would collide every lane's `SOUL.md` onto one basename).
- `tests/test_agent_lanes_check.py` drives the real gate against fixture trees, proving a missing
  lane reds the build naming it and a complete install passes; `tests/test_ci_images.py` proves the
  tag moves when a lane profile changes and the context carries the tree.

## Open items

None. The agent image itself is not rebuilt by this PR (the publish-agent-image workflow is
owner-invoked); this PR ships the Dockerfile steps, the build-time gate, the tag change and the
tests that prove the failure mode.
