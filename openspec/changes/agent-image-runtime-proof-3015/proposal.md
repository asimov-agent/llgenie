# Prove the published agent image is this tree and every bot lane resolves (#3015)

## Why

No agent image has been published since 2026-10-29. On main `fde44d147` (2026-11-23), GHCR
`llgenie/agent:latest` still points at `ea98772a4319…` (created `2026-10-29T09:55:38Z`, no
`llgenie.agent.source` label) while the checkout hashes to `fef0147326e3`. The first dispatch in
weeks, run `45134224656`, is building that hash. The publish lane's post-publish checks only prove
that profile FILES exist and that one model call succeeds; neither proves the tag just published
came from this tree, nor that Hermes can resolve each declared bot lane inside that image. A stale
tag, an unresolvable lane and a bad model credential therefore arrive at the owner as the same
cryptic red.

## What Changes

- Add a `make agent-image-pull` step then a `make agent-image-source-check` step to
  `.github/workflows/publish-agent-image.yml` immediately after `make publish-agent-image`, before
  the existing profile and prompt checks. The pull materialises `:latest` on the runner because
  `buildx --push` does not load a local image; the check reuses `scripts/ci_images.py source_check`
  (issue #2968) — a missing/different `llgenie.agent.source` label is a named failure with both hashes.
- Extend `scripts/agent_image_profiles_check.py` with an opt-in `--resolve` seam: after asserting
  each lane's `config.yaml` exists, call the repository's proven local-only resolution command
  `hermes -p <lane> skills list --source local` for every lane in `agents/manifest.json`, print
  `RESOLVE OK <lane>` / `RESOLVE FAIL <lane>: <reason>`, and exit non-zero on any failure. No model
  key is consumed by this proof.
- Wire `mk/agents.mk::_agent-image-profiles-check` to pass `--resolve`; keep the public
  `agent-image-profiles-check` agent-leg seams unchanged.
- Keep `make hermes-smoke` after both deterministic checks so a real tool-call failure is still
  caught but can no longer be confused with a stale tag or an unresolvable lane.
- Remove the now-stale `agent-image-pull` target exception from
  `tests/fixtures/host-only-wiring.json`: CI reaches the target from the new step, so the recorded
  "no CI job calls it" decision would rot the wiring guard.
- Add hermetic tests for the resolver verdicts and the publish-lane step order, including a
  sabotage proof that the new guards fail against the pre-fix sources.

## Capabilities

- **agent-image-runtime-proof**: the publish lane refuses an image that is not built from the
  current tree and proves every declared bot lane resolves inside it before running the model
  smoke.

## Impact

No engine image, no publish cadence change (the dispatch stays a human act, #2935), no new
credential. The added image-side resolution calls are local-only (`--source local`) and add one
`docker inspect`; the paid prompt smoke remains exactly one call.
