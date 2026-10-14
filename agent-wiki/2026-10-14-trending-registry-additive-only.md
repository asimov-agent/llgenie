# 2026-10-14 vendored registry is additive only (issue #233)

llgenie vendors `data/models.json` verbatim from trending-local-llms and
replaces it wholesale in the weekly `make sync-registry` PR (cron
`17 5 * * 1`). `sync_registry.py check` re-validates the NEW file's shape —
model count, README order, README best-per-backend, link liveness — and cannot
see what the sync LOST. A sync that dropped a key, a model, a measurement
group, a t/s figure or an engagement counter therefore landed green, and the
loss surfaced later as a thin trend list or as `model_engine_pick` ranking
engines from data that no longer exists.

## What was verified before implementing

On the trending-local-llms side the store's own contract does not protect this:
`check_no_removal` compares model IDS only, and the JSON Schema only fails on a
missing REQUIRED key (`additionalProperties: false`). Measured on that repo's
master with `jsonschema`: dropping `engagement.seen_posts` / `buzz_7d`, a
measurement's `hardware`/`quant`/`likes`, or truncating bonsai-2-27b's 13
measurements to 1 all PASSED validation.

## Change

`scripts/registry_keys.py` compares the working copy against the previously
committed one (`HEAD:data/models.json` by default) and fails on a removed
model, a key gone from a model row (list-of-objects compared as a key UNION, so
upstream collapse/reorder is not a false positive), a lost `(engine, hardware)`
measurement group, a lowered t/s, a lowered engagement counter, a lost
`backends` / `supported_engines` member, a lost format, or a removed
engine-registry entry. Additions are always allowed.

`make check-registry-keys` drives it and is part of `make check-registry` (the
CI unit job). `tests/test_registry_keys.py` is wired into `make test-unit`.
`AGENTS.md` gains two durable sections: "The vendored registry is additive
only" and "Agent-implemented issues always end in a monitored, green PR"
(feature branch → PR → monitor the pipeline → fix to green; the merge is a
squash with a proper Conventional Commit message; never merge a red / draft /
under-review PR).

## Verification

- `make check-registry-keys` on the committed registry: `OK: additive only —
  nothing lost vs HEAD:data/models.json (23 models)`, exit 0 (no false
  positive on real data).
- `tests/test_registry_keys.py`: 7 passed in `llgenie/test:latest` — the loss
  matrix (model / optional key / measurement key / measurement group / lowered
  t/s / lowered counter / backend / supported engine / format / engine entry),
  the additive green cases including "a key dropped from ONE row of several is
  NOT reported", the real registry vs itself, both CLI exit codes, and the
  rules/wiring presence.
- `make lint` exit 0; `make openspec-validate
  NAME=trending-registry-additive-only` → "Change ... is valid".
- Red on the pre-change tree: `scripts/registry_keys.py` does not exist there,
  so the tests cannot pass (the guard is new, not a loosened assertion).

## Upstream (trending-local-llms) — the same rule where the store is written

- #114 — `check_no_value_loss` in `scripts/validate.py` (the `removal` stage),
  additive-only for `models.json` + snapshots. Implemented on
  `feat/no-key-loss-guard`.
- #115 — post-refresh data-gap analysis: every sync reports what the data does
  not capture (system RAM/unified memory, KV-cache/context, weight footprint,
  storage offload, engine requirements) and files it as an issue.
- #113 — the issue implementer bot: one implementer per newly-created gap
  issue, PR monitored to green.

- #117 — no dead code: every Python entry point (validator check, script,
  subcommand) must be wired to a `make` target CI runs, bundled into an existing
  stage or as its own target following the same pattern. `_validate-mapped` now
  runs `--only data,schema,mapping,removal`, and
  `tests/test_validate.py::test_every_check_is_wired_to_a_stage_and_a_makefile_target`
  fails on a `check_*` no stage registers or a stage no `--only` list selects.

llgenie never patches the vendored copy to make a sync pass: a loss is reported
upstream and fixed there. On llgenie's side the consumer guard is wired the same
way: `check-registry-keys` is called by `check-registry`, which `make ci-unit`
and `registry-sync.yml` run.
