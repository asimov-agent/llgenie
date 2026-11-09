# Agent image carries the llgenie lane profiles (issue #2181)

2026-11-08. `containers/agent/Dockerfile` — the container every bot lane runs in — carried ZERO
references to `agents/` or to profiles. The image installed the Hermes CLI, git/gh, the docker CLI
and the Nerve supervisory layer, but no lane: a bot job that asked for a named profile resolved
against an empty `${HERMES_HOME}/profiles`. The fleet's rulebooks lived in `agents/<lane>/` (the
tree `make sync-agent-profile` folds into each host profile home) but the image never brought them
in, so a lane ran inside the container with no SOUL.md at all — and nothing noticed until a bot
misbehaved at run time.

Re-measured at `da83db09`: `git grep -n 'agents/' origin/main -- containers/agent` → no matches,
and `agents/manifest.json` declared 13 profiles.

## Fix

The Dockerfile now installs the lanes and refuses a build that is missing one.

- `COPY agents /opt/llgenie/agents` and `COPY agent_lanes_check.py /usr/local/bin/` — the whole
  `agents/` tree (manifest + every profile) comes into the image;
- a new build `RUN` reads `agents/manifest.json` and copies each declared lane into
  `${HERMES_HOME}/profiles/<name>/` (SOUL.md + skills) — the same layout `make sync-agent-profile`
  writes on a host — then runs `scripts/agent_lanes_check.py --agents /opt/llgenie/agents
  --profiles "${HERMES_HOME}/profiles"`, which **FALLS the build**, naming any declared lane whose
  home did not land. The failure is visible at build time, not inside the bot run.
- `scripts/ci_images.py` adds the whole `agents/` tree and `scripts/agent_lanes_check.py` to the
  agent image's **hash inputs**, so a changed SOUL.md or skill moves the `llgenie/agent` tag — a
  stale image that still runs an old lane set is visible in its tag. `context()` places the tree
  under `agents/` in the build context preserving subpaths (a flat copy would have collided every
  lane's `SOUL.md` onto one basename).

The proof of the failure mode lives in `tests/test_agent_lanes_check.py`: a manifest lane absent
from the installed profiles dir makes the real gate exit 1 naming it. Making a stale image visible
was the tag change (`tests/test_ci_images.py::test_agent_tag_changes_when_a_lane_profile_changes`).

Out of scope: other lanes' SOUL content, the engine image, and workflow redesign beyond what the
build step forces — none was needed.
