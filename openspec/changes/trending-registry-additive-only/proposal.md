# Proposal: trending-registry-additive-only

Issues: llgenie #233 (this change) — upstream root: trending-local-llms #114
(the store's own additive-only guard), #115 (post-refresh gap analysis),
#113 (issue implementer bot).

## Why

`data/models.json` is a **verbatim copy** of trending-local-llms'
`data/models.json`, replaced wholesale by the weekly `make sync-registry` PR
(`scripts/sync_registry.py`, cron `17 5 * * 1`). `make check-registry` only
re-validates the NEW file's shape — the model count, the README order, the
links — so it cannot see what the sync **lost**. A sync that dropped a key, a
model, a measurement group, a t/s figure or an engagement counter lands green
and surfaces later as a thin trend list, or as `model_engine_pick` ranking
engines from data that no longer exists.

The rule already exists upstream for the store that OWNS the data
(trending-local-llms #114, `check_no_value_loss` in `scripts/validate.py`,
`make validate-data`). llgenie is the consumer: it must refuse a sync that
shrinks the data, in the same way and for the same reason, and it must never
"repair" upstream data locally to make a sync pass.

Two durable rules land with it, both from the maintainer:

- **an agent-implemented issue is not done until its PR is open, its pipeline
  has been monitored and driven green, and it is squash-merged with a proper
  Conventional Commit message** (one commit per change);
- **every sibling finding is its own issue**, so this change ships only the
  consumer guard.

## What Changes

- `scripts/registry_keys.py` — the guard: `compare(prev, cur)` fails on a
  removed model, a key gone from a model row (list-of-objects compared as a key
  union, so upstream collapses/reorders are not false positives), a lost
  `(engine, hardware)` measurement group, a lowered t/s, a lowered engagement
  counter, a lost `backends` / `supported_engines` member, a lost format, or a
  removed engine-registry entry. CLI: `--prev` (file path or git rev, default
  `HEAD:data/models.json`) and `--cur` (default `data/models.json`).
- `Makefile`: new `check-registry-keys` target, called by `check-registry` (the
  CI unit job), so the weekly sync PR fails when it loses data.
- `tests/test_registry_keys.py`: the loss matrix (each red case + the additive
  green cases), the real vendored registry compared against itself, the CLI
  exit codes, and the rules/wiring presence — wired into `make test-unit`.
- `AGENTS.md`: two durable sections — "The vendored registry is additive only"
  and "Agent-implemented issues always end in a monitored, green PR".

Additions are always allowed; only removals and shrunk values fail. No runtime
behaviour change: the guard runs in CI and reads files.

## Out of scope

- The upstream store guard (`check_no_value_loss`) and the post-refresh
  gap-analysis issue generation: trending-local-llms #114 / #115.
- The issue implementer bot that reacts to newly-created gap issues: #113.
- Filling new requirement dimensions (system RAM, KV-cache, storage offload)
  into the registry: the work items the analysis files upstream.
- Repairing historical loss in the vendored copy: nothing is lost today
  (`make check-registry-keys` is green on the committed registry).

## Impact

`scripts/registry_keys.py` (new), `tests/test_registry_keys.py` (new),
`Makefile` (`check-registry-keys`, `check-registry`, `test-unit` list),
`AGENTS.md`, plus this OpenSpec change and an `agent-wiki/` entry.
