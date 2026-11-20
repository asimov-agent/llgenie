# The agent image carries its tree's source hash; a stale published :latest is named at preflight (issue #2968)

Date: 2026-11-20. Lane: `feat/agent-image-source-stamp-2968`. Issue: #2968.

## What was verified against the spec

- `scripts/ci_images.py`: `build_args("agent")` now returns
  `--build-arg TEST_IMAGE=… --label llgenie.agent.source=<12-hex tag>` — one seam feeding
  BOTH build paths (`_buildx_push` publish, `_build_local` fallback). Pinned by
  `test_agent_publish_stamps_the_source_label` and
  `test_agent_local_build_stamps_the_source_label` (hermetic fake-docker; the stamped tag
  equals the tag the image is pushed under).
- `source_check()` (CLI verb `source-check`): reads the label off the resolved
  `llgenie/agent:latest` with `docker inspect` and compares it with `tag("agent")`.
  Match → rc 0 printing the hash; `<no value>`/empty (every image published before the
  stamp) → rc 1 naming the tree hash + the remedy (dispatch `publish-agent-image.yml` on
  main, issue #2935); a hash from a different tree → rc 1 naming BOTH hashes. Pinned by
  three verdict tests; `tests/test_ci_images.py` 48/48 green.
- `make agent-image-source-check` (`mk/agents.mk`) wraps the verb; the composite
  `.github/actions/agent-leg/action.yml` runs it in preflight BEFORE `make hermes-smoke`,
  under the same `routing_smoke` guard — pinned by
  `test_agent_leg_source_check_precedes_the_routing_smoke`. A leg that would crash
  hermes-smoke with `Profile 'llgenie-status-keeper' does not exist` (the three
  issue-bot failures on 2026-11-20: runs 44715391118, 44717110622, 44717111523) now
  fails at job start with the root cause named.

## Key decisions

- One stamp seam (`build_args`) instead of touching each build call: the spec requires
  every agent build path to carry the label, and a future third path inherits it.
- The check is strict from the first run: unlabeled published images ARE the stale state
  today's failures proved; no grace mode (AGENTS: no fallback paths).
- The preflight step inherits the `routing_smoke` opt-in: only legs that reach
  `hermes-smoke` can die on a stale profile, so only those legs gate; legs that don't
  smoke are behaviorally unchanged.
- Publish cadence unchanged: moving `:latest` stays the human dispatch (#2935); this
  lane only makes the lag legible.

## Current status

Implementation complete on the branch, all pinned tests green; OpenSpec change
`agent-image-source-stamp` validated; full unit battery + preflight run before push.
