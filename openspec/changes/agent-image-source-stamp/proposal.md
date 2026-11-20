# Stamp the agent image's source hash — name a stale published agent:latest at preflight

## Why

Every agent leg starts with `scripts/ci_images.py ensure agent`, which pulls the floating
`ghcr.io/<registry>/llgenie/agent:latest` (run 44717111523, main `ad37eeada`, 2026-11-20).
`:latest` only moves when a human dispatches `publish-agent-image.yml` (#2935), so between
dispatches the tree's agent wiring (profiles, Hermes pin, Dockerfile) drifts from the published
image with no signal. The drift surfaces mid-job as a cryptic crash — `[hermes-smoke] FAIL: hermes
exited 1` / `Error: Profile 'llgenie-status-keeper' does not exist` (`mk/agents.mk:149`) — that
misattributes an infrastructure state to the lane's own code. Three issue-bot failures on
2026-11-20 (runs 44715391118, 44717110622, 44717111523) all died this way. The repo already
computes the agent image's content hash (`ci_images.tag("agent")` = 12 hex over the Dockerfile,
lockfiles, the agents/ tree and the test base tag) but nothing carries it INTO the image, so a
resolved image cannot be checked against the tree that pulled it (issue #2968).

## What Changes

- `scripts/ci_images.py` stamps the agent build with `--label llgenie.agent.source=<12-hex tag>`
  in BOTH build paths (`_buildx_push` for publish, `_build_local` for the local fallback), so
  every image built after this change carries its source hash.
- Add `scripts/ci_images.py source-check agent` (new CLI verb): read the label off the resolved
  local agent image via `docker inspect` and compare it with the tree's computed tag. Match → rc 0;
  label missing or different → rc 1 naming the two hashes and the remedy (dispatch
  `publish-agent-image.yml` on main, issue #2935). Previously published images carry no label and
  are therefore stale from the first run — exactly the state today's failures prove.
- Add `make agent-image-source-check` (`mk/agents.mk`) wrapping that verb.
- Wire it into `.github/actions/agent-leg/action.yml` as a preflight step between the credential
  proof and `make hermes-smoke` (same `routing_smoke` opt-in as the smoke step): a stale image
  fails at job start with the root cause named and never reaches `hermes-smoke`.
- Hermetic tests pin the stamp on both build paths, the three check verdicts, and the preflight
  ordering.

## Capabilities

- **agent-image-source-stamp**: the agent image carries its tree's source hash, and the agent-leg
  preflight refuses a published image that does not carry it.

## Impact

No engine image is touched; no publish cadence changes (the dispatch stays a human act, #2935).
Legs that opt into `routing_smoke` gain one cheap local check (a `docker inspect`) before the
smoke they already run. The first such leg after this lands names the staleness until the owner
dispatches the publish (#2935) — by design.
