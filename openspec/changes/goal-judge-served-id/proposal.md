# Proposal: goal-judge-served-id

Issue: #3089

## Why

Hermes pauses a goal after five judge transport failures when `auxiliary.goal_judge` is pinned to a Strata model the local server is not serving. An explicit auxiliary provider does not walk top-level `fallback_providers`. `agents/hermes-base-config.yaml` is the one config this repo merges into every llgenie lane, and on `origin/main` it named no Strata id and no `goal_judge`.

## What Changes

- `agents/hermes-base-config.yaml` gains `auxiliary.goal_judge`: provider `custom`, model `qwen3.8-flash-next-iq3_xxs`, base URL `http://127.0.0.1:8080/v1`, and a `fallback_chain` copied from the existing Nous `fallback_providers`. The judge entry carries no `key_env`. The live-profile spelling `custom:strata` is not used here: this file has no named strata provider, and Hermes resolves an auxiliary task's own `provider: custom` plus `base_url` as the anonymous local route.
- `scripts/apply_hermes_base_config.py` owns that key. A merge writes it and leaves every other `auxiliary` task in place. `model.default` stays `meituan/longcat-2.5:free`.
- `tests/test_apply_hermes_base_config.py` locks the served id, the Nous chain, the missing judge `key_env`, and the surviving foreign auxiliary task.

## Impact

Lane and image provision both run this seam, so the next apply stamps the served id. No credential value is written. The local id is not added to `model.aliases` or `fallback_providers`, so the Nous catalog check does not see it.

## Not covered

- Live `~/.hermes` profiles. Those were corrected on the host on 2026-11-27 and are not this repository.
- trending-local-llms issue #1798, which renders the same pin through that repo's model chain.
- Issue #3026 (Nous catalog or budget drift).
