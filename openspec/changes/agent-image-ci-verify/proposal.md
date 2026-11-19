# Build the agent image with the 0.23.2 + profile-chain configuration — and make the build lane prove the image it publishes answers a prompt

## Why

Measured on main `81e6de6e8` (2026-11-19): the only Hermes prompt test in the repo, `make hermes-smoke`,
appears in **no** CI job (`grep -n 'hermes-smoke' .github/workflows/*.yml` = 0 matches), and running it
against the published `ghcr.io/asimov-agent/llgenie/agent:latest` (image id `ea98772a4319`) fails inside
the image: `Profile 'llgenie-status-keeper' does not exist` — the published image predates the profile
work and carries no lane profiles. #2932 pinned Hermes v0.23.2 in the agent Dockerfile and #2929 moved
every bot invocation onto per-profile model chains, yet `publish-agent-image.yml` (the dispatch-only lane
that builds and pushes `llgenie/agent`) only **builds + pushes**: nothing in CI asks the freshly built
image whether its 13 manifest profiles landed or whether Hermes answers a prompt through its profile's
own model chain. A broken publish today is discovered by the next live bot run. GitHub issue: #2934.

## What changes

- **New check seam** `scripts/agent_image_profiles_check.py` + `make agent-image-profiles-check`: runs
  the built/published agent image and asserts that every profile named in `agents/manifest.json` (all
  13, incl. `llgenie-status-keeper`) exists inside it at `$HERMES_HOME/profiles/<lane>/config.yaml`;
  fails the lane naming each missing lane.
- **The build-agent CI lane gains a verification half** (`publish-agent-image.yml`): after the publish
  step, the same job runs `make agent-image-profiles-check` against the just-published `:latest`, then
  `make hermes-smoke` — the repo's existing real-prompt proof (one Hermes call that must use its tool,
  nonce asserted from the transcript) — with `NOUS_API_KEY` from `secrets.NOUS_PORTAL_API_TOKEN`, the
  same credential every other agent lane passes. Post-#2929 the smoke call carries no `-m` flag: the
  model chain comes from the profile's own `config.yaml`.
- **Local dry-run proof** (user-approved): an agent image built from the #2929 chain tree on the host
  must pass `hermes-smoke` before the lane is trusted (issue #2934 AC3).

Out of scope (separate linked issue #2935): the owner's `workflow_dispatch` of
`publish-agent-image.yml` on merged main and the GHCR tag-pair verification after that publish —
dispatching this lane is a human act (#2837 precedent).

## Impact

- Affected spec: `agent-image-ci` (ADDED requirements: post-publish profile-presence check,
  post-publish prompt smoke, both reached only through Makefile targets).
- Affected code: `.github/workflows/publish-agent-image.yml`, `mk/agents.mk`, `Makefile` roster,
  `scripts/agent_image_profiles_check.py` (new), `scripts/package-layers.json`,
  `tests/test_agent_image_profiles_check.py` (new), `tests/test_ci_images.py` (lane-step ordering
  assertion), `docs/BOTS.md`, `agent-wiki/`, `docs/changes.d/`.
- No new secrets; `publish-agent-image.yml` stays dispatch-only (discipline allow-list entry
  `AGENT_LANES["publish-agent-image.yml"]` already covers Hermes use in this lane).
