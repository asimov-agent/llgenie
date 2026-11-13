# Proposal: sync-registry-alias-lock

## Why

Upstream trending-local-llms added the optional per-row property `measurement_model_aliases`
(contract commit `447a9fa83`, applied to row `qwen3.6-35b-a3b` -> `["qwen3.8-27b"]` by `41539762d`).
Issue #2647 was filed claiming `scripts/sync_registry.py::normalise()` would drop it on the next
store sync. Measured at `298552b58`, the claim's mechanism is FALSE: `normalise()` copies each row
wholly (`row = dict(row)`, `out = dict(data)`), so the key survives — a live-upstream probe through
`validate()+normalise()` shows `qwen3.6-35b-a3b` keeping `['qwen3.8-27b']`, and
`registry_keys.compare(committed, normalised)` reports 0 alias-related losses (its 773 loss lines
are the known #2503 store-age drift, none alias-related).

What is missing is the LOCK: no test pins the preservation. A future normalise() refactor to
field-by-row rebuild — exactly the shape #2647 assumed — would then silently drop the attribution
the new contract exists to carry. This change adds that lock test (the real deliverable of #2647).

## What Changes

- `tests/test_registry_normalise.py` gains a hermetic test: a synthetic alias-carrying row goes
  through `sync_registry.normalise()`, the alias survives byte-for-byte, rows without the key do
  not gain one, and `registry_keys.compare()` reports no alias-related loss between the committed
  and the normalised stores.
- No production-code change: `normalise()` already preserves the key; the test locks it.

## Not covered

- The 24 store-age drift lines `registry_keys.compare` reports between the committed store (last
  synced 2026-11-12) and today's live upstream sync — that is issue #2503's engagement-refresh
  scope, not this lane. (An earlier partial probe that omitted the measurements store produced a
  spurious README-engine rejection; the full CLI sync including `--measurements` is accepted rc=0.)

## Impact

- Affected specs: `registry-sync` (ADDED requirement: alias preservation is locked by a test)
- Affected code: `tests/test_registry_normalise.py` only
