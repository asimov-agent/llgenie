# Re-pin two drifted Hermes model-chain members (issue #3026)

## Why

The weekly `make check-agent-model-catalog` alarm on issue #3026 named two drifts in
`agents/hermes-base-config.yaml`: `qwen/qwen4-max:free` is no longer in the live Nous
catalog (every bot leg that hops to its alias pays a 404), and
`stepfun/step-3.7-flash:free` commits `context_window: 262144` while the published
`context_length` is 256000, mis-sizing sessions. The business-analyst decision on the
issue (comment 7193200443) already chose both drop-in targets; this change only
implements that decision.

## What changes

- Re-pin the `nous-qwen4max` alias and `fallback_providers[2]` from
  `qwen/qwen4-max:free` to `tencent/hy4-flash:free`, keeping the 1000000 token budget
  (published context_length 1048576 >= 1000000). A YAML comment records that this is a
  deliberate duplicate: `tencent/hy4-flash:free` already names `nous-hy4` and
  `fallback_providers[0]`, so two chain slots point at the same live catalog id on
  purpose, as a no-404 fallback for the retired member.
- Keep the `stepfun/step-3.7-flash:free` id and change only its `context_window`
  262144 -> 256000 so the committed budget equals the published context_length.
- Run `make apply-hermes-base-config --all` so every profile home and the agent image
  build re-read the chain.

## Impact

- Affected specs: `agent-model-chain` (modified — two members' pins).
- Affected code: `agents/hermes-base-config.yaml`, plus the derived per-profile configs
  and agent-image chain produced by `make apply-hermes-base-config --all`.
- Verification: `make check-agent-model-catalog` (rc=0; the retired id is an expected
  persistent 404 in the real catalog) and `make agent-image-profiles-check` (rc=0).

## Out of scope

Re-deciding the chosen targets, replacing any other chain member, or touching the
catalog checker itself. No side issue is required: nothing is deferred here.
