# agent-image-lane-profiles

## ADDED Requirements

### Requirement: the image installs every manifest-declared lane

When the agent image is built, each profile that `agents/manifest.json` declares must be copied
from the COPYed `agents/` tree into `${HERMES_HOME}/profiles/<name>/` (SOUL.md + skill files),
mirroring how `make sync-agent-profile` populates a host profile home — a bot job asking for a
named lane must resolve against a profiles directory that actually holds that lane's rulebook.

#### Scenario: a build installs all declared lanes

Given a build whose `/opt/llgenie/agents/manifest.json` declares `llgenie-planner` and an
`/opt/llgenie/agents/llgenie-planner/` tree carrying a `SOUL.md`; when the Dockerfile
lane-install `RUN` runs; then `llgenie-planner`'s files land in
`${HERMES_HOME}/profiles/llgenie-planner/`, including `SOUL.md`.

### Requirement: a missing lane fails the build

`scripts/agent_lanes_check.py`, run by the build after the install, must return non-zero naming
every profile that `agents/manifest.json` declares whose home is absent from the installed
profiles directory. That is a build failure, not a warning — an image that would run a lane with
no rulebook must not be produced.

#### Scenario: a declared lane absent from the installed set reds the build

Given a manifest declaring `llgenie-planner` and `llgenie-security`, and an installed profiles
dir holding only `llgenie-security/SOUL.md`; when `scripts/agent_lanes_check.py --agents <agents>
--profiles <profiles>` runs; then it exits non-zero and its stderr names `llgenie-planner` as the
missing lane and states that the image carries it with no rulebook.

#### Scenario: a complete install passes

Given a manifest declaring lanes and an installed profiles dir holding a `SOUL.md` for each; when
`scripts/agent_lanes_check.py` runs; then it exits 0 and prints an OK line.

### Requirement: a changed lane profile moves the image tag

The whole `agents/` tree must be an input to the agent image's content-hash tag, so editing any
lane's `SOUL.md` or skill changes `llgenie/agent`'s tag — a stale image that keeps running an old
lane set is visible in its tag instead of being pulled silently forever.

#### Scenario: editing a lane's SOUL.md changes the agent tag

Given the agent image inputs; when a lane's `SOUL.md` in `agents/` is changed and the tag is
computed again; then the tag differs from the value before the edit, and both match 12 lowercase
hex digits.
